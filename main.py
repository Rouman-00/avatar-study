from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}
    
@app.post('/chat')
def chat():
    data = request.get_json(force=True)
    message = data.get('message', '').strip()
    use_llm = data.get('use_llm', True)

    if not message:
        return jsonify({'error': 'Leere Nachricht'}), 400

    response_text, emotion = 'Hallo, ich bin ein Avatar mit Lippensynchronisation, der gesprochene Inhalte in Echtzeit visuell nachbildet. Meine Mundbewegungen orientieren sich dabei an der Spracheingabe, sodass der Eindruck entsteht, ich würde tatsächlich sprechen.', 'neutral'

    return jsonify({
        'response': response_text,
        'emotion': emotion,
    })

app.mount("/", StaticFiles(directory="static", html=True), name="static")