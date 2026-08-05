import mimetypes

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import base64

# Windows/Python often has no entry for .mjs and StaticFiles falls back to
# text/plain, which browsers refuse to load as an ES module (blocks all
# TalkingHead imports with no console error).
mimetypes.add_type('text/javascript', '.mjs')

# v1beta1 is required here: SSML <mark> timepointing (enable_time_pointing /
# response.timepoints) is not exposed by the stable v1 client.
from google.cloud import texttospeech_v1beta1 as texttospeech

app = FastAPI()

tts_client = texttospeech.TextToSpeechClient()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

class UserInput(BaseModel): 
    message: str
    use_llm: bool = True

@app.post('/chat')
def chat(user_input: UserInput):
    message = user_input.message.strip()
    # use_llm = user_input.use_llm

    if not message:
        return ({'error': 'Leere Nachricht'}), 400

    response_text, emotion = 'Hello, i am a talking avatar with lip synchronization. My mouth movements are based on the speech input, creating the impression that I am actually speaking.', 'neutral'

    return ({
        'response': response_text,
        'emotion': emotion,
    })


@app.post('/tts')
async def tts(request: Request):
    data = await request.json()
    ssml = data.get('input', {}).get('ssml', '')
    voice_name = data.get('voice', {}).get('name', 'en-US-Neural2-A')
    language_code = data.get('voice', {}).get('languageCode', 'en-US')

    if not ssml.strip():
        return {'error': 'Kein Text'}, 400

    synth_request = texttospeech.SynthesizeSpeechRequest(
        input=texttospeech.SynthesisInput(ssml=ssml),
        voice=texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        ),
        # Ask Google to time the <mark> tags TalkingHead put into the SSML.
        enable_time_pointing=[texttospeech.SynthesizeSpeechRequest.TimepointType.SSML_MARK],
    )

    # synthesize_speech is a blocking gRPC call; run it off the event loop.
    response = await asyncio.to_thread(tts_client.synthesize_speech, request=synth_request)

    audio_content = base64.b64encode(response.audio_content).decode('utf-8')
    timepoints = [
        {'markName': tp.mark_name, 'timeSeconds': round(tp.time_seconds, 3)}
        for tp in response.timepoints
    ]

    return {'audioContent': audio_content, 'timepoints': timepoints}

app.mount("/", StaticFiles(directory="static", html=True), name="static")