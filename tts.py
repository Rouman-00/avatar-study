import asyncio
import os

# v1beta1 is required here: SSML <mark> timepointing (enable_time_pointing /
# response.timepoints) is not exposed by the stable v1 client.
from google.cloud import texttospeech_v1beta1 as texttospeech
from google.oauth2 import service_account

import config


def get_tts_client() -> texttospeech.TextToSpeechClient:
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        # In der .env hinterlegte Pfade sind oft relativ zum Projekt gemeint,
        # nicht zum Verzeichnis, aus dem uvicorn gestartet wird -> hier
        # explizit relativ zum Projektverzeichnis aufloesen, damit es auf
        # jedem Rechner funktioniert.
        if not os.path.isabs(creds_path):
            creds_path = str((config.BASE_DIR / creds_path).resolve())
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        return texttospeech.TextToSpeechClient(credentials=credentials)

    # Kein Service-Account-JSON hinterlegt -> Client-Bibliothek faellt
    # automatisch auf die Application Default Credentials zurueck (z.B. per
    # `gcloud auth application-default login` angemeldeter Nutzer).
    return texttospeech.TextToSpeechClient()


tts_client = get_tts_client()


async def synthesize(ssml: str, voice_name: str, language_code: str):
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
    return await asyncio.to_thread(tts_client.synthesize_speech, request=synth_request)
