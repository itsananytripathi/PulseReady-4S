"""Explicit, server-side ElevenLabs text-to-speech adapter."""

from __future__ import annotations

import httpx

from app.config import settings
from app.integrations.external_clients import (
    ExternalProviderError,
    IntegrationUnavailable,
    live_call_allowed,
)


MAX_BRIEFING_CHARACTERS = 4000
MAX_AUDIO_BYTES = 20 * 1024 * 1024


async def synthesize_speech(*, text: str) -> bytes:
    """Generate MP3 audio only after an explicit, gated live request."""
    if not text or len(text) > MAX_BRIEFING_CHARACTERS:
        raise ValueError("Briefing text must be between 1 and 4000 characters.")
    if not live_call_allowed("elevenlabs"):
        raise IntegrationUnavailable("ElevenLabs live synthesis is not enabled or configured.")
    voice_id = settings.elevenlabs_voice_id
    model_id = settings.elevenlabs_model_id or "eleven_multilingual_v2"
    endpoint = (settings.elevenlabs_api_endpoint or "").rstrip("/")
    if endpoint != "https://api.elevenlabs.io" or not voice_id:
        raise IntegrationUnavailable("ElevenLabs endpoint and voice are not configured.")

    try:
        async with httpx.AsyncClient(
            base_url=endpoint,
            timeout=settings.external_http_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": settings.elevenlabs_api_key or "", "Accept": "audio/mpeg"},
                json={"text": text, "model_id": model_id},
            )
    except httpx.TimeoutException as exc:
        raise ExternalProviderError("ElevenLabs request timed out.") from exc
    except httpx.HTTPError as exc:
        raise ExternalProviderError("ElevenLabs request failed.") from exc

    if not 200 <= response.status_code < 300:
        raise ExternalProviderError("ElevenLabs returned an unsuccessful response.")
    audio = response.content
    if not audio or len(audio) > MAX_AUDIO_BYTES or not audio.startswith(b"ID3") and not audio.startswith(b"\xff\xfb"):
        raise ExternalProviderError("ElevenLabs returned invalid audio.")
    return audio
