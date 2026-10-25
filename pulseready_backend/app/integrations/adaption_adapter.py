"""Optional Adaption Labs SDK adapter for PulseReady 4S.

The installed SDK exposes dataset adaptation operations. It does not expose a
direct operational-alert or summary hallucination-review method, so that
workflow remains explicitly unavailable and fails closed.
"""

import asyncio
import logging
import math
import os
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class AdaptionUnavailable(RuntimeError):
    """Adaption is disabled or not configured."""


class AdaptionJobError(RuntimeError):
    """A documented Adaption dataset operation failed or was malformed."""


def _enabled() -> bool:
    """Use the existing explicit integration allowlist as the feature switch."""
    return (
        getattr(settings, "integration_mode", "live") == "live"
        and getattr(settings, "integrations_enabled", True)
        and getattr(settings, "adaption_enabled", True)
        and "adaption_labs" in settings.enabled_integrations
    )


def _api_key_configured() -> bool:
    key = settings.adaption_labs_api_key
    return bool(key) and not key.startswith("YOUR_")


def is_configured() -> bool:
    """Check configuration without initializing the SDK or calling a network."""
    return _enabled() and _api_key_configured()


def _new_client():
    """Initialize the official SDK lazily so backend startup remains optional."""
    if not _enabled():
        raise AdaptionUnavailable("Adaption integration is disabled.")
    if not _api_key_configured():
        raise AdaptionUnavailable("Adaption API key is not configured.")

    try:
        from adaption import Adaption
    except ImportError as exc:
        raise AdaptionUnavailable("The Adaption SDK is not installed.") from exc

    options: dict[str, Any] = {
        "api_key": settings.adaption_labs_api_key,
        "timeout": settings.external_http_timeout_seconds,
    }
    if settings.adaption_labs_endpoint and not settings.adaption_labs_endpoint.startswith("YOUR_"):
        options["base_url"] = settings.adaption_labs_endpoint
    try:
        return Adaption(**options)
    except Exception as exc:
        logger.warning("Adaption SDK initialization failed.")
        raise AdaptionUnavailable("Could not initialize Adaption SDK.") from exc


def _safe_status(status_obj: Any) -> str:
    value = getattr(status_obj, "status", None)
    allowed = {"pending", "running", "awaiting_input", "succeeded", "failed"}
    if not isinstance(value, str) or value.lower() not in allowed:
        raise AdaptionJobError("Adaption returned an invalid status.")
    return value.lower()


def _safe_credits(estimate: Any) -> float:
    value = getattr(estimate, "estimated_credits_consumed", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        raise AdaptionJobError("Adaption returned an invalid estimate.")
    return float(value)


def _job_timeout_seconds() -> int:
    raw = os.getenv("ADAPTION_JOB_TIMEOUT_SECONDS", "3600")
    try:
        timeout = int(raw)
    except ValueError as exc:
        raise AdaptionUnavailable("ADAPTION_JOB_TIMEOUT_SECONDS must be an integer.") from exc
    if not 1 <= timeout <= 3600:
        raise AdaptionUnavailable("Adaption job timeout must be between 1 and 3600 seconds.")
    return timeout


def _run_adaptation_sync(
    dataset_id: str,
    column_mapping: dict,
    job_specification: dict,
    estimate_only: bool,
    timeout_seconds: int,
) -> dict:
    client = _new_client()

    try:
        if estimate_only:
            estimate = client.datasets.adapt(
                dataset_id,
                column_mapping=column_mapping,
                job_specification=job_specification,
                estimate=True,
            )
            return {
                "mode": "estimate",
                "dataset_id": dataset_id,
                "estimated_credits_consumed": _safe_credits(estimate),
            }

        run = client.datasets.adapt(
            dataset_id,
            column_mapping=column_mapping,
            job_specification=job_specification,
        )
        run_id = getattr(run, "run_id", None)
        if not isinstance(run_id, str) or not run_id:
            raise AdaptionJobError("Adaption did not return a valid run identifier.")

        status = _safe_status(client.datasets.wait_for_completion(dataset_id, timeout=timeout_seconds))
        if status == "failed":
            logger.warning("Adaption dataset job failed.")
            raise AdaptionJobError("Adaption dataset job failed.")
        if status != "succeeded":
            raise AdaptionJobError("Adaption did not return a completed job status.")
        return {"mode": "run", "dataset_id": dataset_id, "run_id": run_id, "status": status}
    except (AdaptionUnavailable, AdaptionJobError):
        raise
    except Exception as exc:
        logger.warning("Adaption dataset operation failed.")
        raise AdaptionJobError("Adaption dataset operation failed.") from exc
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


async def run_dataset_adaptation(
    *,
    dataset_id: str,
    column_mapping: dict,
    job_specification: dict,
    estimate_only: bool = True,
) -> dict:
    """Run a documented dataset adaptation operation off the event loop."""
    if not is_configured():
        raise AdaptionUnavailable("Adaption is disabled or missing its API key.")
    if not dataset_id or dataset_id.startswith("YOUR_"):
        raise AdaptionUnavailable("A verified dataset ID is required.")
    timeout_seconds = _job_timeout_seconds()
    return await asyncio.to_thread(
        _run_adaptation_sync,
        dataset_id,
        column_mapping,
        job_specification,
        estimate_only,
        timeout_seconds,
    )


async def review_operational_summary(*, alert_id: str, summary: str, evidence: list[str]) -> dict:
    """Return a labelled offline fixture or fail closed in live mode."""
    if getattr(settings, "integration_mode", "live") == "mock":
        return {
            "provider": "mock",
            "mode": "mock",
            "review_status": "simulated",
            "approved": False,
            "reviewed_text": None,
            "issues": ["Mock result only: no real Adaption review was performed."],
        }
    raise AdaptionUnavailable(
        "Single-summary review is not implemented. The installed Adaption SDK "
        "documents dataset adaptation, not direct alert-summary verification."
    )
