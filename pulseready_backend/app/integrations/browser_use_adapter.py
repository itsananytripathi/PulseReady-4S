"""Optional Browser Use Cloud V4 hosted-agent adapter.

This module intentionally does not expose Browser Use credentials or add a
route. Callers must opt in through ``ENABLED_INTEGRATIONS=browser_use`` and a
server-side ``BROWSER_USE_API_KEY``. V4 model selection is left to the
service by omitting model and model parameters, and every run is capped at
one US dollar.
"""

import asyncio
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

MAX_COST_USD = 1.0
TERMINAL_SUCCESS_STATUSES = {"completed", "succeeded", "success"}
TERMINAL_FAILURE_STATUSES = {"failed", "cancelled", "canceled", "timed_out", "timeout"}


class BrowserUseUnavailable(RuntimeError):
    """Browser Use is disabled, unconfigured, or unavailable."""


class BrowserUseRunError(RuntimeError):
    """A Browser Use run failed validation or did not complete successfully."""


def is_configured() -> bool:
    """Return whether a live call is explicitly enabled and configured."""
    key = settings.browser_use_api_key
    return (
        getattr(settings, "integration_mode", "live") == "live"
        and getattr(settings, "integrations_enabled", True)
        and
        "browser_use" in settings.enabled_integrations
        and bool(key)
        and not key.startswith("YOUR_")
    )


def _new_client() -> Any:
    if not is_configured():
        raise BrowserUseUnavailable("Browser Use is disabled or not configured.")

    try:
        from browser_use_sdk.v4 import BrowserUse
    except ImportError as exc:
        raise BrowserUseUnavailable("The browser-use-sdk V4 package is not installed.") from exc

    options: dict[str, Any] = {"api_key": settings.browser_use_api_key}
    if settings.browser_use_endpoint and not settings.browser_use_endpoint.startswith("YOUR_"):
        options["base_url"] = settings.browser_use_endpoint

    try:
        return BrowserUse(**options)
    except Exception as exc:
        logger.warning("Browser Use SDK initialization failed.")
        raise BrowserUseUnavailable("Could not initialize Browser Use SDK.") from exc


def _status(result: Any) -> str:
    value = getattr(result, "status", None)
    if not isinstance(value, str) or not value.strip():
        raise BrowserUseRunError("Browser Use returned no valid run status.")
    return value.strip().lower()


def _output(result: Any) -> Any:
    value = getattr(result, "output", None)
    if value is None:
        value = getattr(result, "result", None)
    if value is None:
        raise BrowserUseRunError("Browser Use completed without a result.")
    return value


def _run_sync(task: str) -> dict[str, Any]:
    client = _new_client()
    try:
        # Do not pass model or modelParams: V4 selects its documented default.
        created = client.runs.create(task, max_cost_usd=MAX_COST_USD)
        run_id = getattr(created, "id", None)
        if not isinstance(run_id, str) or not run_id:
            raise BrowserUseRunError("Browser Use did not return a valid run identifier.")

        completed = client.runs.wait_for_completion(run_id)
        status = _status(completed)
        if status in TERMINAL_FAILURE_STATUSES:
            raise BrowserUseRunError(f"Browser Use run ended with status: {status}.")
        if status not in TERMINAL_SUCCESS_STATUSES:
            raise BrowserUseRunError(f"Browser Use run did not complete: {status}.")

        return {"run_id": run_id, "status": status, "output": _output(completed)}
    except (BrowserUseUnavailable, BrowserUseRunError):
        raise
    except Exception as exc:
        logger.warning("Browser Use run failed without exposing provider details.")
        raise BrowserUseRunError("Browser Use run failed.") from exc
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


async def run_hosted_task(*, task: str) -> dict[str, Any]:
    """Run one bounded V4 hosted-agent task off the event loop.

    A caller timeout does not cancel a remote run; use ``cancel_run`` when an
    abandoned run must be explicitly cancelled. This adapter never retries an
    ambiguous create call.
    """
    if not isinstance(task, str) or not task.strip():
        raise BrowserUseRunError("Browser Use task must be a non-empty string.")
    return await asyncio.to_thread(_run_sync, task.strip())


def cancel_run(*, run_id: str) -> None:
    """Cancel an abandoned run through the SDK when supported."""
    if not run_id:
        raise BrowserUseRunError("A run identifier is required for cancellation.")
    client = _new_client()
    try:
        cancel = getattr(client.runs, "cancel", None)
        if not callable(cancel):
            raise BrowserUseUnavailable("The installed Browser Use SDK cannot cancel runs.")
        cancel(run_id)
    except (BrowserUseUnavailable, BrowserUseRunError):
        raise
    except Exception as exc:
        logger.warning("Browser Use cancellation failed without exposing provider details.")
        raise BrowserUseRunError("Browser Use cancellation failed.") from exc
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
