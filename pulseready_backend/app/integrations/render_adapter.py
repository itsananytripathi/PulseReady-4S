"""Read-only Render API operations.

The adapter implements only the documented service-listing operation. It never
creates, updates, deploys, or deletes Render resources.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.integrations.external_clients import (
    ExternalProviderError,
    IntegrationUnavailable,
    live_call_allowed,
)


async def list_services(*, limit: int = 20) -> list[dict[str, Any]]:
    """List Render services through the explicitly enabled live integration."""
    if not 1 <= limit <= 100:
        raise ValueError("Render service limit must be between 1 and 100.")
    if not live_call_allowed("render"):
        raise IntegrationUnavailable("Render live service listing is not enabled or configured.")
    if (settings.render_api_endpoint or "").rstrip("/") != "https://api.render.com":
        raise IntegrationUnavailable("Render endpoint must be https://api.render.com.")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.render_api_token}",
    }
    try:
        async with httpx.AsyncClient(
            base_url="https://api.render.com",
            timeout=settings.external_http_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.get("/v1/services", params={"limit": limit}, headers=headers)
    except httpx.TimeoutException as exc:
        raise ExternalProviderError("Render request timed out.") from exc
    except httpx.HTTPError as exc:
        raise ExternalProviderError("Render request failed.") from exc

    if not 200 <= response.status_code < 300:
        raise ExternalProviderError("Render returned an unsuccessful response.")
    try:
        payload = response.json()
    except (ValueError, TypeError) as exc:
        raise ExternalProviderError("Render returned malformed JSON.") from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ExternalProviderError("Render returned an invalid service list.")
    return payload
