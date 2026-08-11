import time

import config  # noqa: F401 -- muss vor faster_whisper importiert werden (CUDA/HF-Setup)

from faster_whisper import WhisperModel

WHISPER_MODELS = {
    "medium": config.WHISPER_MODEL_MEDIUM,
    "small": config.WHISPER_MODEL_SMALL,
}

_whisper_models: dict[tuple[str, str], WhisperModel] = {}


def get_whisper_model(device: str, model_size: str = "medium") -> WhisperModel:
    model_id = WHISPER_MODELS.get(model_size, config.WHISPER_MODEL_MEDIUM)
    key = (device, model_id)
    if key not in _whisper_models:
        compute_type = "float16" if device == "cuda" else "int8"
        print(f"[stt] Lade Whisper-Modell '{model_id}' auf '{device}' (compute_type={compute_type}) ...", flush=True)
        start = time.monotonic()
        _whisper_models[key] = WhisperModel(model_id, device=device, compute_type=compute_type)
        print(f"[stt] Modell auf '{device}' geladen nach {time.monotonic() - start:.1f}s", flush=True)
    return _whisper_models[key]


def transcribe_file(
    device: str,
    path: str,
    model_size: str = "medium",
    beam_size: int = 5,
    vad_filter: bool = False,
) -> str:
    model = get_whisper_model(device, model_size)
    print(
        f"[stt] Starte Transkription auf '{device}' (model={model_size}, beam_size={beam_size}, vad_filter={vad_filter}) ...",
        flush=True,
    )
    start = time.monotonic()
    segments, _info = model.transcribe(path, beam_size=beam_size, vad_filter=vad_filter)
    text = "".join(segment.text for segment in segments).strip()
    print(f"[stt] Transkription auf '{device}' fertig nach {time.monotonic() - start:.1f}s ({len(text)} Zeichen)", flush=True)
    return text
