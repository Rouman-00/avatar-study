"""ElevenLabs TTS backend.

TalkingHead speaks exclusively in Google's dialect: it posts SSML with one
<mark name='N'/> per word and expects {audioContent, timepoints} back.
ElevenLabs understands neither SSML nor marks -- but its /with-timestamps
endpoint returns per-character timings. So the SSML is flattened to plain
text while remembering the character offset of every mark, and the character
timings are folded back into mark timepoints. That keeps the /tts contract
towards the browser identical for both providers.
"""
import asyncio
import base64
import xml.etree.ElementTree as ET

import aiohttp
from fastapi import HTTPException

import config


class ElevenLabsError(HTTPException):
    """HTTPException carrying a reason code, so callers can log/route it."""

    def __init__(self, status_code: int, reason: str, message: str):
        super().__init__(status_code=status_code, detail=message)
        self.reason = reason


def ssml_to_text_and_marks(ssml: str) -> tuple[str, list[tuple[str, int]]]:
    """Flatten TalkingHead's SSML into plain text plus (markName, charIndex).

    The mark sits *before* its word ("Hello <mark name='1'/>world"), so the
    offset recorded when the mark is reached is exactly the index of the
    first character of the word it labels.
    """
    root = ET.fromstring(ssml)

    parts: list[str] = []
    marks: list[tuple[str, int]] = []
    length = 0

    def append(text: str | None) -> None:
        nonlocal length
        if text:
            parts.append(text)
            length += len(text)

    append(root.text)
    for child in root:
        tag = child.tag.rsplit("}", 1)[-1]  # drop a namespace prefix if present
        if tag == "mark":
            marks.append((child.get("name") or "", length))
        elif tag == "break":
            # ElevenLabs has no <break>; a dash keeps a comparable pause and
            # stays inside the character alignment.
            append(" - ")
        append(child.tail)

    return "".join(parts), marks


def _marks_to_timepoints(marks, alignment) -> list[dict]:
    starts = (alignment or {}).get("character_start_times_seconds") or []
    if not starts:
        return []

    timepoints = []
    for mark_name, char_index in marks:
        index = min(max(char_index, 0), len(starts) - 1)
        timepoints.append(
            {"markName": mark_name, "timeSeconds": round(float(starts[index]), 3)}
        )
    return timepoints


def _describe_error(status: int, body) -> tuple[str, str]:
    """Map an ElevenLabs error response onto (reason, German message).

    Both error shapes are handled: the documented {"detail": {"status": ...,
    "message": ...}} and the plain {"detail": "..."} that some endpoints and
    the gateway return.
    """
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        reason = str(detail.get("status") or "")
        api_message = str(detail.get("message") or "")
    elif isinstance(detail, str):
        reason, api_message = "", detail
    else:
        reason, api_message = "", str(body)[:400]

    # Kontingent aufgebraucht: ElevenLabs meldet das je nach Plan als 401
    # quota_exceeded ODER als 402 payment_required/insufficient_credits.
    if reason in {"quota_exceeded", "insufficient_credits", "payment_required"} or status == 402:
        return (
            reason or "quota_exceeded",
            "ElevenLabs-Kontingent aufgebraucht (keine Credits mehr). "
            f"Originalmeldung: {api_message}",
        )

    if reason in {"invalid_api_key", "missing_api_key"} or status == 401:
        return (
            reason or "authentication_error",
            "ElevenLabs-API-Key ungueltig oder fehlt (ELEVENLABS_API_KEY in der .env pruefen). "
            f"Originalmeldung: {api_message}",
        )

    if reason == "detected_unusual_activity":
        return (
            reason,
            "ElevenLabs hat den Account wegen ungewoehnlicher Aktivitaet gesperrt "
            f"(Free-Tier-Sperre). Originalmeldung: {api_message}",
        )

    if reason == "voice_not_found" or status == 404:
        return (
            reason or "not_found",
            f"ElevenLabs kennt diese Voice-ID nicht. Originalmeldung: {api_message}",
        )

    if status == 429:
        return (
            reason or "rate_limit_error",
            "ElevenLabs-Ratenlimit bzw. zu viele gleichzeitige Anfragen. "
            f"Originalmeldung: {api_message}",
        )

    if status == 400:
        return (
            reason or "validation_error",
            f"ElevenLabs hat die Anfrage abgelehnt (ungueltige Parameter): {api_message}",
        )

    if status >= 500:
        return (
            reason or "service_unavailable",
            f"ElevenLabs-Server nicht erreichbar oder gestoert (HTTP {status}): {api_message}",
        )

    return (reason or "unknown_error", f"ElevenLabs-Fehler (HTTP {status}): {api_message}")


async def synthesize(ssml: str, voice_id: str) -> dict:
    """Return {'audioContent': b64, 'timepoints': [...]} for the given SSML."""
    if not config.ELEVENLABS_API_KEY:
        raise ElevenLabsError(
            500,
            "missing_api_key",
            "ELEVENLABS_API_KEY ist nicht gesetzt. Bitte in der .env-Datei hinterlegen.",
        )

    try:
        text, marks = ssml_to_text_and_marks(ssml)
    except ET.ParseError as exc:
        raise ElevenLabsError(400, "invalid_ssml", f"SSML nicht parsebar: {exc}")

    if not text.strip():
        raise ElevenLabsError(400, "empty_text", "Kein Text zum Synthetisieren.")

    url = (
        f"{config.ELEVENLABS_API_BASE}/text-to-speech/{voice_id}/with-timestamps"
        f"?output_format={config.ELEVENLABS_OUTPUT_FORMAT}"
    )
    payload = {
        "text": text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": config.ELEVENLABS_VOICE_SETTINGS,
    }
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=config.ELEVENLABS_TIMEOUT_SECONDS)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    try:
                        body = await response.json(content_type=None)
                    except Exception:
                        body = await response.text()
                    reason, message = _describe_error(response.status, body)
                    raise ElevenLabsError(502, reason, message)

                data = await response.json(content_type=None)
    except asyncio.TimeoutError:
        raise ElevenLabsError(
            504,
            "timeout",
            f"ElevenLabs hat innerhalb von {config.ELEVENLABS_TIMEOUT_SECONDS}s nicht geantwortet.",
        )
    except aiohttp.ClientError as exc:
        raise ElevenLabsError(502, "connection_error", f"Verbindung zu ElevenLabs fehlgeschlagen: {exc}")

    audio_b64 = data.get("audio_base64")
    if not audio_b64:
        # 200 ohne Audio ist laut Doku nicht vorgesehen, kommt aber vor, wenn
        # ein Proxy/Gateway die Antwort veraendert -- hier nicht still
        # durchreichen, sonst schweigt der Avatar kommentarlos.
        raise ElevenLabsError(502, "empty_response", "ElevenLabs hat HTTP 200 ohne Audiodaten geliefert.")

    # Sanity check: b64-Dekodierbarkeit hier pruefen statt erst im Browser.
    try:
        base64.b64decode(audio_b64, validate=True)
    except Exception as exc:
        raise ElevenLabsError(502, "invalid_audio", f"Audiodaten unlesbar: {exc}")

    return {
        "audioContent": audio_b64,
        "timepoints": _marks_to_timepoints(marks, data.get("alignment")),
    }
