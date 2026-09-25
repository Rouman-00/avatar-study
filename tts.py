"""TTS facade: routes /tts to the currently selected provider.

Both providers answer in the same shape ({audioContent, timepoints}) so the
browser side (TalkingHead) never learns which one produced the audio. The
provider is global server state, switched from the control panel via
POST /tts/provider.
"""
import asyncio
import base64
import os

# v1beta1 is required here: SSML <mark> timepointing (enable_time_pointing /
# response.timepoints) is not exposed by the stable v1 client.
from google.cloud import texttospeech_v1beta1 as texttospeech
from google.oauth2 import service_account

import config
import elevenlabs_tts

PROVIDERS = ("elevenlabs", "google")

_provider = (
    config.TTS_PROVIDER_DEFAULT if config.TTS_PROVIDER_DEFAULT in PROVIDERS else "elevenlabs"
)

# Letzter TTS-Fehler, damit das Control-Panel ihn anzeigen kann: TalkingHead
# verschluckt fehlgeschlagene /tts-Aufrufe im Browser kommentarlos (der Avatar
# schweigt dann einfach), der Versuchsleiter wuerde sonst nichts sehen.
_last_error: dict | None = None

# Wecker fuer die SSE-Verbindungen (/tts/events): statt dass das Panel im
# Sekundentakt fragt, wartet es hier und wird bei einer echten Aenderung
# geweckt. Beim Wecken wird das Event ERSETZT, nicht zurueckgesetzt -- so
# bekommen alle bereits wartenden Verbindungen ihr set() mit, waehrend neue
# Wartende sofort das frische Event greifen und nichts verpassen.
_change_event = asyncio.Event()


def get_change_event() -> asyncio.Event:
    return _change_event


def _notify_change() -> None:
    global _change_event
    previous, _change_event = _change_event, asyncio.Event()
    previous.set()


def snapshot() -> dict:
    """Der Zustand, den das Control-Panel sieht."""
    return {"provider": _provider, "lastError": _last_error}


def get_provider() -> str:
    return _provider


def set_provider(provider: str) -> str:
    global _provider
    if provider not in PROVIDERS:
        raise ValueError(f"Unbekannter TTS-Anbieter: {provider}")
    if provider != _provider:
        _provider = provider
        print(f"[tts] Anbieter gewechselt auf: {_provider}", flush=True)
        _notify_change()
    return _provider


def get_last_error() -> dict | None:
    return _last_error


def record_error(provider: str, reason: str, message: str) -> None:
    global _last_error
    error = {"provider": provider, "reason": reason, "message": message}
    print(f"[tts] FEHLER ({provider}/{reason}): {message}", flush=True)
    if error != _last_error:
        _last_error = error
        _notify_change()


def clear_error() -> None:
    # Laeuft nach JEDEM erfolgreichen /tts -- nur wecken, wenn wirklich ein
    # Fehler verschwindet, sonst wuerde jede Aeusserung die SSE-Schleifen
    # unnoetig durchlaufen lassen.
    global _last_error
    if _last_error is not None:
        _last_error = None
        _notify_change()


# --- Google ------------------------------------------------------------

_google_client: texttospeech.TextToSpeechClient | None = None


def get_tts_client() -> texttospeech.TextToSpeechClient:
    """Google TTS client, created on first use.

    Lazy on purpose: without this, a missing gcloud login would crash the
    import and take the whole server down even when ElevenLabs is selected.
    """
    global _google_client
    if _google_client is not None:
        return _google_client

    creds_path = config.GOOGLE_APPLICATION_CREDENTIALS
    if creds_path:
        # In der .env hinterlegte Pfade sind oft relativ zum Projekt gemeint,
        # nicht zum Verzeichnis, aus dem uvicorn gestartet wird -> hier
        # explizit relativ zum Projektverzeichnis aufloesen, damit es auf
        # jedem Rechner funktioniert.
        if not os.path.isabs(creds_path):
            creds_path = str((config.BASE_DIR / creds_path).resolve())
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        _google_client = texttospeech.TextToSpeechClient(credentials=credentials)
    else:
        # Kein Service-Account-JSON hinterlegt -> Client-Bibliothek faellt
        # automatisch auf die Application Default Credentials zurueck (z.B. per
        # `gcloud auth application-default login` angemeldeter Nutzer).
        _google_client = texttospeech.TextToSpeechClient()

    return _google_client


async def synthesize(ssml: str, voice_name: str, language_code: str):
    client = get_tts_client()
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
    return await asyncio.to_thread(client.synthesize_speech, request=synth_request)


async def synthesize_google(ssml: str, voice_name: str, language_code: str) -> dict:
    response = await synthesize(ssml, voice_name, language_code)
    return {
        "audioContent": base64.b64encode(response.audio_content).decode("utf-8"),
        "timepoints": [
            {"markName": tp.mark_name, "timeSeconds": round(tp.time_seconds, 3)}
            for tp in response.timepoints
        ],
    }


# --- Dispatch ----------------------------------------------------------


def resolve_voice(provider: str, requested: str | None) -> str:
    """Pick the voice to use for a provider.

    The browser always sends whatever sits in the control panel's voice
    dropdown. If that value does not belong to the active provider (e.g.
    a Google voice name right after switching to ElevenLabs), fall back to
    the provider's default instead of failing the request.
    """
    if provider == "elevenlabs":
        known = {voice["id"] for voice in config.ELEVENLABS_VOICES}
        if requested in known:
            return requested
        return config.ELEVENLABS_VOICE_DEFAULT

    known = {voice["name"] for voice in config.GOOGLE_TTS_VOICES}
    if requested in known:
        return requested
    return config.GOOGLE_TTS_VOICE_DEFAULT
