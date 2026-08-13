import asyncio
import base64
import mimetypes
import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config  # noqa: F401 -- muss zuerst importiert werden (env/CUDA-Setup)
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
    await asyncio.to_thread(stt.get_whisper_model, "cpu", "medium")


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
    device: str = Form("cpu"),
    model_size: str = Form("medium"),
    beam_size: int = Form(5),
    vad_filter: bool = Form(False),
):
    if device not in ("cpu", "cuda"):
        device = "cpu"
    if model_size not in stt.WHISPER_MODELS:
        model_size = "medium"
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


@app.post('/tts')
async def tts_endpoint(request: Request):
    data = await request.json()
    ssml = data.get('input', {}).get('ssml', '')
    voice_name = data.get('voice', {}).get('name', 'en-US-Neural2-A')
    language_code = data.get('voice', {}).get('languageCode', 'en-US')

    if not ssml.strip():
        return {'error': 'Kein Text'}, 400

    response = await tts.synthesize(ssml, voice_name, language_code)

    audio_content = base64.b64encode(response.audio_content).decode('utf-8')
    timepoints = [
        {'markName': tp.mark_name, 'timeSeconds': round(tp.time_seconds, 3)}
        for tp in response.timepoints
    ]

    return {'audioContent': audio_content, 'timepoints': timepoints}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
