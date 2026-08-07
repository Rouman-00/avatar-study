import time

import config  # noqa: F401 -- muss vor faster_whisper importiert werden (CUDA/HF-Setup)

from faster_whisper import WhisperModel

_whisper_models: dict[str, WhisperModel] = {}


def get_whisper_model(device: str) -> WhisperModel:
    if device not in _whisper_models:
        compute_type = "float16" if device == "cuda" else "int8"
        print(f"[stt] Lade Whisper-Modell '{config.WHISPER_MODEL_ID}' auf '{device}' (compute_type={compute_type}) ...", flush=True)
        start = time.monotonic()
        _whisper_models[device] = WhisperModel(
            config.WHISPER_MODEL_ID, device=device, compute_type=compute_type
        )
        print(f"[stt] Modell auf '{device}' geladen nach {time.monotonic() - start:.1f}s", flush=True)
    return _whisper_models[device]


def transcribe_file(device: str, path: str) -> str:
    model = get_whisper_model(device)
    print(f"[stt] Starte Transkription auf '{device}' ...", flush=True)
    start = time.monotonic()
    segments, _info = model.transcribe(path)
    text = "".join(segment.text for segment in segments).strip()
    print(f"[stt] Transkription auf '{device}' fertig nach {time.monotonic() - start:.1f}s ({len(text)} Zeichen)", flush=True)
    return text
