import json
import os
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class Settings:
    database_url: str
    api_keys: Mapping[str, str]
    max_upload_bytes: int
    max_signal_age_hours: int
    max_future_skew_minutes: int

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
    )

settings = get_settings()
