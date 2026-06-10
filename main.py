from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

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

    response_text, emotion = 'Hallo, ich bin ein Avatar mit Lippensynchronisation, der gesprochene Inhalte in Echtzeit visuell nachbildet. Meine Mundbewegungen orientieren sich dabei an der Spracheingabe, sodass der Eindruck entsteht, ich würde tatsächlich sprechen.', 'neutral'

    return ({
        'response': response_text,
        'emotion': emotion,
    })


@app.post('/tts')
async def tts(request: Request):
    data = await request.json()
    ssml = data.get('input', {}).get('ssml', '')
    voice_name = data.get('voice', {}).get('name', 'de-DE-Standard-A')
    return {"status": "TTS request received"}

app.mount("/", StaticFiles(directory="static", html=True), name="static")