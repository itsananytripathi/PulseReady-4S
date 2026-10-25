"""Central, fail-closed policy for optional external integrations."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import settings


class IntegrationUnavailable(RuntimeError):
    """An integration is disabled, incomplete, or unavailable."""


class ExternalProviderError(RuntimeError):
    """A provider call failed without exposing provider details."""


INTEGRATION_SPECS = {
    "agent37_cloud": {
        "secret_field": "agent37_cloud_api_key",
        "endpoint_field": "agent37_cloud_endpoint",
        "contract_verified": False,
        "mock_ready": False,
    },
    "agent37_personal": {
        "secret_field": "agent37_personal_api_key",
        "endpoint_field": "agent37_personal_endpoint",
        "contract_verified": False,
        "mock_ready": False,
    },
    "adaption_labs": {
        "secret_field": "adaption_labs_api_key",
        "endpoint_field": "adaption_labs_endpoint",
        "contract_verified": True,
        "mock_ready": True,
    },
    "render": {
        "secret_field": "render_api_token",
        "endpoint_field": "render_api_endpoint",
        "contract_verified": True,
        "mock_ready": False,
    },
    "nodus_compute": {
        "secret_field": "nodus_compute_api_key",
        "endpoint_field": "nodus_compute_endpoint",
        "contract_verified": False,
        "mock_ready": False,
    },
    "elevenlabs": {
        "secret_field": "elevenlabs_api_key",
        "endpoint_field": "elevenlabs_api_endpoint",
        "contract_verified": True,
        "mock_ready": (Path(__file__).resolve().parents[1] / "assets" / "demo_briefing.mp3").is_file(),
    },
    "browser_use": {
        "secret_field": "browser_use_api_key",
        "endpoint_field": "browser_use_endpoint",
        "contract_verified": True,
        "mock_ready": True,
    },
    "flutterflow": {
        "secret_field": "flutterflow_api_key",
        "endpoint_field": "flutterflow_endpoint",
        "contract_verified": False,
        "mock_ready": True,
    },
}


def integration_statuses() -> list[dict[str, object]]:
    """Return non-secret capability diagnostics for operations/admin tooling."""
    statuses: list[dict[str, object]] = []
    for name, spec in INTEGRATION_SPECS.items():
        secret = getattr(settings, spec["secret_field"], None)
        endpoint = getattr(settings, spec["endpoint_field"], None)
        secret_configured = bool(secret) and not str(secret).startswith("YOUR_")
        endpoint_configured = bool(endpoint) and not str(endpoint).startswith("YOUR_")
        if name == "elevenlabs":
            voice_id = getattr(settings, "elevenlabs_voice_id", None)
            model_id = getattr(settings, "elevenlabs_model_id", None)
            endpoint_configured = endpoint_configured and bool(voice_id) and not str(voice_id).startswith("YOUR_")
            endpoint_configured = endpoint_configured and bool(model_id) and not str(model_id).startswith("YOUR_")
        if name == "render" and endpoint_configured:
            endpoint_configured = urlparse(str(endpoint)).hostname == "api.render.com"
        enabled = name in settings.enabled_integrations
        if settings.integration_mode == "mock" and spec["mock_ready"]:
            status = "mock_active"
            enabled = True
            message = "Mock adapter is available; no provider call is made."
        elif settings.integration_mode == "mock":
            status = "unsupported_contract"
            message = "No verified provider operation or local mock adapter is available."
            if name == "elevenlabs":
                message = "Local demo MP3 is missing; live ElevenLabs is not called in mock mode."
        elif not enabled:
            status = "disabled"
            message = "Provider is not explicitly enabled for live execution."
        elif not secret_configured or not endpoint_configured:
            status = "missing_credential" if not secret_configured else "configuration_error"
            message = "Required provider configuration is incomplete."
        elif not spec["contract_verified"]:
            status = "unsupported_contract"
            message = "Provider credentials are present, but this operation has no verified contract."
        elif not settings.integrations_enabled:
            status = "disabled"
            message = "Global live integration enablement is off."
        else:
            status = "live_ready"
            message = "Configuration and provider contract are ready; no live check has been performed."
        statuses.append({
            "capability": name,
            "status": status,
            "mode": settings.integration_mode,
            "enabled": enabled,
            "credential_configured": secret_configured,
            "endpoint_configured": endpoint_configured,
            "contract_verified": bool(spec["contract_verified"]),
            "message": message,
        })
    return statuses


def live_call_allowed(service: str, *, require_endpoint: bool = True) -> bool:
    """Return whether this process may make a live provider request."""
    if settings.integration_mode != "live" or not settings.integrations_enabled:
        return False
    if service not in settings.enabled_integrations:
        return False
    spec = INTEGRATION_SPECS.get(service)
    if spec is None:
        return False
    key = getattr(settings, spec["secret_field"], None)
    if not key or key.startswith("YOUR_"):
        return False
    if require_endpoint:
        endpoint = getattr(settings, spec["endpoint_field"], None)
        if not endpoint or endpoint.startswith("YOUR_"):
            return False
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
            return False
    return True


def require_live_call(service: str, *, require_endpoint: bool = True) -> None:
    if settings.integration_mode == "mock":
        raise IntegrationUnavailable("External integrations are disabled in mock mode.")
    if not settings.integrations_enabled:
        raise IntegrationUnavailable("External integrations are globally disabled.")
    if not live_call_allowed(service, require_endpoint=require_endpoint):
        raise IntegrationUnavailable(f"{service} integration is not configured.")


def create_provider_client(service: str) -> httpx.AsyncClient:
    """Create a bounded client only after server-side configuration checks."""
    require_live_call(service)
    spec = INTEGRATION_SPECS[service]
    endpoint = getattr(settings, spec["endpoint_field"])
    return httpx.AsyncClient(
        base_url=endpoint,
        timeout=settings.external_http_timeout_seconds,
        follow_redirects=False,
    )


async def request_json(service: str, *, method: str, path: str, **kwargs):
    """Make one bounded provider request without retries or body logging.

    Paths are intentionally relative and must be selected by trusted server
    code; absolute or user-supplied destination URLs are rejected.
    """
    if not path.startswith("/") or "://" in path:
        raise IntegrationUnavailable("Provider paths must be fixed relative paths.")
    client = create_provider_client(service)
    try:
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ExternalProviderError("External provider request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ExternalProviderError("External provider request failed.") from exc
        if not 200 <= response.status_code < 300:
            raise ExternalProviderError("External provider returned an unsuccessful response.")
        try:
            return response.json()
        except (ValueError, TypeError) as exc:
            raise ExternalProviderError("External provider returned malformed JSON.") from exc
    finally:
        await client.aclose()
