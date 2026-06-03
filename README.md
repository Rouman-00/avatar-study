# Avatar Study

Browser-based application for a lab study. An animated 3D avatar with lip-sync conducts dialogues with study participants. 

Using Talkinghead: TalkingHead provides the 3D avatar renderer with real-time lip sync and procedural facial animation
(https://github.com/met4citizen/TalkingHead)
---

## Requirements

- Python 3.10+
- Google Chrome or Microsoft Edge (for WebGL + Web Speech API)
- VS Code with the **Live Server** extension
- API keys for LLM & TTS/STT

---

## One-time Setup

### 1 — Install Python dependencies

```bash
conda create -n avatar-study python=3.10
conda activate avatar-study
pip install -r requirements.txt
```

---

## Start

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
### Web/Backend server

### VS Code — Live Server

Right-click `index.html` → **Open with Live Server**

It usually opens at `http://127.0.0.1:5500/index.html`.

---

## Dependencies & Acknowledgements

This project uses [TalkingHead](https://github.com/met4citizen/TalkingHead)
by [met4citizen](https://github.com/met4citizen), licensed under the
[MIT License](https://github.com/met4citizen/TalkingHead/blob/main/LICENSE).

TalkingHead provides the 3D avatar renderer with real-time lip sync and procedural facial animation.
