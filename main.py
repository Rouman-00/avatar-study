import re

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import edge_tts
import base64

app = FastAPI()

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

    response_text, emotion = 'Hallo, ich bin ein Avatar mit Lippensynchronisation. Meine Mundbewegungen orientieren sich dabei an der Spracheingabe, sodass der Eindruck entsteht, ich würde tatsächlich sprechen.', 'neutral'

    return ({
        'response': response_text,
        'emotion': emotion,
    })


@app.post('/tts')
async def tts(request: Request):
    data = await request.json()
    ssml = data.get('input', {}).get('ssml', '')
    voice_name = data.get('voice', {}).get('name', 'de-DE-Standard-A')
    plain_text = re.sub(r'<[^>]+>', ' ', ssml)
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()

    if not plain_text:
        return {'error': 'Kein Text'}, 400

    marks = re.findall(r'<mark name="(\d+)"', ssml)
    print(f"SSML: {ssml}")
    communicate = edge_tts.Communicate(plain_text, voice='de-DE-ConradNeural')
    audio_data = b''
    word_times = []
    async for chunk in communicate.stream():
        if chunk['type'] == 'audio':
            audio_data += chunk['data']
        elif chunk['type'] == 'WordBoundary':
            word_times.append(chunk['offset'] / 10_000_000)

    audio_content = base64.b64encode(audio_data).decode('utf-8')

    # Mark N → Startzeitpunkt von Wort N
    timepoints = [
        {'markName': mark_name, 'timeSeconds': round(word_times[i], 3)}
        for i, mark_name in enumerate(marks)
        if i < len(word_times)
    ]

    return {'audioContent': audio_content, 'timepoints': timepoints}

app.mount("/", StaticFiles(directory="static", html=True), name="static")