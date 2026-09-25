import asyncio
import json
import mimetypes
import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config  # muss zuerst importiert werden (env/CUDA-Setup)
import db
import elevenlabs_tts
import interview
import llm
import stt
import tts

# Windows/Python often has no entry for .mjs and StaticFiles falls back to
# text/plain, which browsers refuse to load as an ES module (blocks all
# TalkingHead imports with no console error).
mimetypes.add_type('text/javascript', '.mjs')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def preload_stt_model():
    # Vermeidet, dass der erste Transkriptions-Request die ~7s Ladezeit des
    # Whisper-Modells (medium, CPU) live mit abbekommt.
    await asyncio.to_thread(stt.get_whisper_model, config.STT_DEVICE, config.STT_MODEL_SIZE)


@app.on_event("startup")
async def init_database():
    db.init_db()


class UserInput(BaseModel):
    message: str
    use_llm: bool = True


@app.post('/chat')
async def chat(user_input: UserInput):
    message = user_input.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Leere Nachricht")

    if not user_input.use_llm:
        raise HTTPException(
            status_code=400, detail="LLM-Modus ist deaktiviert. Bitte im Control-Panel aktivieren."
        )

    try:
        response_text = await llm.generate_reply(message)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM-Anfrage fehlgeschlagen: {exc}")

    return {'response': response_text, 'emotion': 'neutral'}


@app.post('/api/transcribe')
async def transcribe(
    audio: UploadFile = File(...),
    device: str = Form(config.STT_DEVICE),
    model_size: str = Form(config.STT_MODEL_SIZE),
    beam_size: int = Form(config.STT_BEAM_SIZE),
    vad_filter: bool = Form(config.STT_VAD_FILTER),
):
    if device not in ("cpu", "cuda"):
        device = config.STT_DEVICE
    if model_size not in stt.WHISPER_MODELS:
        model_size = config.STT_MODEL_SIZE
    beam_size = max(1, min(10, beam_size))

    print(
        f"[api] /api/transcribe: device={device}, model_size={model_size}, beam_size={beam_size}, "
        f"vad_filter={vad_filter}, filename={audio.filename}",
        flush=True,
    )

    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        text = await asyncio.to_thread(
            stt.transcribe_file, device, tmp_path, model_size, beam_size, vad_filter
        )
        return {'text': text}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Transkription fehlgeschlagen ({device}): {exc}"
        )
    finally:
        os.remove(tmp_path)


class TtsProviderInput(BaseModel):
    provider: str


@app.get('/tts/config')
async def tts_config():
    """Stimmen-Pools + aktiver Anbieter fuer die Auswahllisten im Control-Panel."""
    return {
        'provider': tts.get_provider(),
        'providers': list(tts.PROVIDERS),
        'google': {
            'languageCode': config.GOOGLE_TTS_LANGUAGE_CODE,
            'voices': config.GOOGLE_TTS_VOICES,
            'default': config.GOOGLE_TTS_VOICE_DEFAULT,
        },
        'elevenlabs': {
            'voices': config.ELEVENLABS_VOICES,
            'default': config.ELEVENLABS_VOICE_DEFAULT,
            'modelId': config.ELEVENLABS_MODEL_ID,
            'apiKeyConfigured': bool(config.ELEVENLABS_API_KEY),
        },
    }


@app.post('/tts/provider')
async def set_tts_provider(payload: TtsProviderInput):
    try:
        provider = tts.set_provider(payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Der alte Fehler gehoert zum vorherigen Anbieter und wuerde sonst
    # weiter im Control-Panel stehen bleiben.
    tts.clear_error()
    return {'provider': provider}


@app.get('/tts/status')
async def tts_status():
    """Momentaufnahme des TTS-Zustands.

    Das Control-Panel bezieht den Zustand ueber /tts/events; diese Route
    bleibt fuer schnelle Kontrollen von Hand (curl) und als Rueckfallebene.
    """
    return tts.snapshot()


# Wie lange eine SSE-Verbindung ohne Aenderung wartet, bevor ein
# Kommentar-Ping rausgeht. Haelt Verbindung und Zwischenschichten wach und
# laesst abgebrochene Clients auffliegen.
SSE_KEEPALIVE_SECONDS = 20


@app.get('/tts/events')
async def tts_events(request: Request):
    """Server-Sent Events: meldet TTS-Fehler und Anbieterwechsel ans Panel.

    Noetig, weil TalkingHead im Browser einen fehlgeschlagenen /tts-Aufruf
    stillschweigend verwirft -- der Avatar schweigt dann einfach, ohne dass
    irgendwo eine Meldung auftaucht. Und zwar per Push statt per Polling:
    der Fehler tritt im ANDEREN Fenster (index.html) auf, das Panel kann ihn
    nicht selbst bemerken, soll aber auch nicht im Sekundentakt nachfragen.
    """

    async def event_stream():
        last_payload = None

        while True:
            if await request.is_disconnected():
                break

            # Das Event VOR dem Lesen greifen: aendert sich der Zustand
            # zwischen Lesen und Warten, ist es bereits gesetzt und das
            # wait() kehrt sofort zurueck, statt die Aenderung zu verpassen.
            change = tts.get_change_event()
            payload = tts.snapshot()

            if payload != last_payload:
                last_payload = payload
                yield f"data: {json.dumps(payload)}\n\n"

            try:
                await asyncio.wait_for(change.wait(), timeout=SSE_KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"  # Kommentarzeile, vom Client ignoriert

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            # Falls spaeter ein Reverse Proxy davorsteht: nicht puffern,
            # sonst kommen die Events erst gebuendelt an.
            'X-Accel-Buffering': 'no',
        },
    )


@app.post('/tts')
async def tts_endpoint(request: Request):
    data = await request.json()
    ssml = data.get('input', {}).get('ssml', '')
    requested_voice = data.get('voice', {}).get('name')
    language_code = data.get('voice', {}).get('languageCode', config.GOOGLE_TTS_LANGUAGE_CODE)

    if not ssml.strip():
        raise HTTPException(status_code=400, detail='Kein Text')

    provider = tts.get_provider()
    voice = tts.resolve_voice(provider, requested_voice)

    if provider == 'elevenlabs':
        try:
            result = await elevenlabs_tts.synthesize(ssml, voice)
        except elevenlabs_tts.ElevenLabsError as exc:
            # Bewusst kein stiller Fallback auf Google: ein Stimmwechsel
            # mitten im Gespraech wuerde die Studienbedingung verfaelschen.
            tts.record_error('elevenlabs', exc.reason, str(exc.detail))
            raise
        except Exception as exc:
            tts.record_error('elevenlabs', 'unexpected_error', str(exc))
            raise HTTPException(status_code=502, detail=f'ElevenLabs-TTS fehlgeschlagen: {exc}')
    else:
        try:
            result = await tts.synthesize_google(ssml, voice, language_code)
        except Exception as exc:
            tts.record_error('google', 'google_error', str(exc))
            raise HTTPException(status_code=502, detail=f'Google-TTS fehlgeschlagen: {exc}')

    tts.clear_error()
    return result

app.mount("/", StaticFiles(directory="static", html=True), name="static")
