import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from dotenv import load_dotenv


# Load only the backend-local development file. Existing process variables win,
# and production deployments should provide secrets through their environment.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
SUPPORTED_INTEGRATIONS = frozenset({
    "agent37_cloud",
    "agent37_personal",
    "adaption_labs",
    "render",
    "nodus_compute",
    "elevenlabs",
    "browser_use",
    "flutterflow",
})


def parse_cors_origins(raw: str | None) -> tuple[str, ...]:
    """Parse exact browser origins without ever widening to a wildcard."""
    if raw is None:
        return DEFAULT_CORS_ORIGINS
    values = tuple(item.strip() for item in raw.split(","))
    if not values or any(not item for item in values):
        raise RuntimeError("CORS_ORIGINS must contain at least one explicit origin")
    for origin in values:
        parsed = urlparse(origin)
        if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("CORS_ORIGINS must contain explicit http(s) origins")
        if parsed.path or parsed.params or parsed.query or parsed.fragment:
            raise RuntimeError("CORS_ORIGINS entries must be origin-only URLs")
    return values


def optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def parse_enabled_integrations(raw: str | None) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return ()
    values = tuple(dict.fromkeys(item.strip().lower() for item in raw.split(",") if item.strip()))
    unknown = sorted(set(values) - SUPPORTED_INTEGRATIONS)
    if unknown:
        raise RuntimeError(f"ENABLED_INTEGRATIONS contains unsupported names: {', '.join(unknown)}")
    return values


def parse_timeout_seconds(raw: str | None) -> float:
    value = raw or "10"
    try:
        timeout = float(value)
    except ValueError as exc:
        raise RuntimeError("EXTERNAL_HTTP_TIMEOUT_SECONDS must be a number") from exc
    if not 0.1 <= timeout <= 120:
        raise RuntimeError("EXTERNAL_HTTP_TIMEOUT_SECONDS must be between 0.1 and 120 seconds")
    return timeout


def parse_integration_mode(raw: str | None) -> str:
    value = (raw or "mock").strip().lower()
    if value not in {"mock", "live"}:
        raise RuntimeError("INTEGRATION_MODE must be 'mock' or 'live'")
    return value


def parse_bool(raw: str | None, *, default: bool = False) -> bool:
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError("INTEGRATIONS_ENABLED must be a boolean")

@dataclass(frozen=True)
class Settings:
    database_url: str
    api_keys: Mapping[str, str]
    max_upload_bytes: int
    max_signal_age_hours: int
    max_future_skew_minutes: int
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    external_http_timeout_seconds: float = 10.0
    enabled_integrations: tuple[str, ...] = ()
    integration_mode: str = "mock"
    integrations_enabled: bool = False
    adaption_enabled: bool = False
    agent37_cloud_api_key: str | None = None
    agent37_cloud_endpoint: str | None = None
    agent37_personal_api_key: str | None = None
    agent37_personal_endpoint: str | None = None
    adaption_labs_api_key: str | None = None
    adaption_labs_endpoint: str | None = None
    render_api_token: str | None = None
    render_api_endpoint: str | None = None
    nodus_compute_api_key: str | None = None
    nodus_compute_endpoint: str | None = None
    elevenlabs_api_key: str | None = None
    elevenlabs_api_endpoint: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str | None = None
    browser_use_api_key: str | None = None
    browser_use_endpoint: str | None = None
    flutterflow_api_key: str | None = None
    flutterflow_endpoint: str | None = None

def get_settings() -> Settings:
    raw = os.getenv("PULSEREADY_API_KEYS", '{"demo-key-change-me":"11111111-1111-4111-8111-111111111111"}')
    try:
        keys = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("PULSEREADY_API_KEYS must be a JSON object") from exc
    if not isinstance(keys, dict) or not keys:
        raise RuntimeError("PULSEREADY_API_KEYS must be a non-empty JSON object")
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./pulseready.db"),
        api_keys={str(k): str(v) for k, v in keys.items()},
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", "2000000")),
        max_signal_age_hours=int(os.getenv("MAX_SIGNAL_AGE_HOURS", "72")),
        max_future_skew_minutes=int(os.getenv("MAX_FUTURE_SKEW_MINUTES", "10")),
        cors_origins=parse_cors_origins(os.getenv("CORS_ORIGINS")),
        external_http_timeout_seconds=parse_timeout_seconds(os.getenv("EXTERNAL_HTTP_TIMEOUT_SECONDS")),
        enabled_integrations=parse_enabled_integrations(os.getenv("ENABLED_INTEGRATIONS")),
        integration_mode=parse_integration_mode(os.getenv("INTEGRATION_MODE")),
        integrations_enabled=parse_bool(os.getenv("INTEGRATIONS_ENABLED")),
        adaption_enabled=parse_bool(os.getenv("ADAPTION_ENABLED")),
        agent37_cloud_api_key=optional_env("AGENT37_CLOUD_API_KEY"),
        agent37_cloud_endpoint=optional_env("AGENT37_CLOUD_ENDPOINT"),
        agent37_personal_api_key=optional_env("AGENT37_PERSONAL_API_KEY"),
        agent37_personal_endpoint=optional_env("AGENT37_PERSONAL_ENDPOINT"),
        adaption_labs_api_key=optional_env("ADAPTION_LABS_API_KEY"),
        adaption_labs_endpoint=optional_env("ADAPTION_LABS_ENDPOINT"),
        render_api_token=optional_env("RENDER_API_TOKEN"),
        render_api_endpoint=optional_env("RENDER_API_ENDPOINT"),
        nodus_compute_api_key=optional_env("NODUS_COMPUTE_API_KEY"),
        nodus_compute_endpoint=optional_env("NODUS_COMPUTE_ENDPOINT"),
        elevenlabs_api_key=optional_env("ELEVENLABS_API_KEY"),
        elevenlabs_api_endpoint=optional_env("ELEVENLABS_API_ENDPOINT"),
        elevenlabs_voice_id=optional_env("ELEVENLABS_VOICE_ID"),
        elevenlabs_model_id=optional_env("ELEVENLABS_MODEL_ID"),
        browser_use_api_key=optional_env("BROWSER_USE_API_KEY"),
        browser_use_endpoint=optional_env("BROWSER_USE_ENDPOINT"),
        flutterflow_api_key=optional_env("FLUTTERFLOW_API_KEY"),
        flutterflow_endpoint=optional_env("FLUTTERFLOW_ENDPOINT"),
    )

settings = get_settings()
