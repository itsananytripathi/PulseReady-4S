import asyncio
from types import SimpleNamespace

import pytest

from app.integrations import browser_use_adapter as adapter


def configured(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "settings",
        SimpleNamespace(
            enabled_integrations=("browser_use",),
            browser_use_api_key="bu_synthetic_key",
            browser_use_endpoint=None,
        ),
    )


def test_disabled_and_placeholder_key_fail_closed(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "settings",
        SimpleNamespace(enabled_integrations=(), browser_use_api_key=None, browser_use_endpoint=None),
    )
    assert adapter.is_configured() is False
    with pytest.raises(adapter.BrowserUseUnavailable):
        adapter._new_client()

    configured(monkeypatch)
    monkeypatch.setattr(adapter.settings, "browser_use_api_key", "YOUR_API_KEY_HERE", raising=False)
    assert adapter.is_configured() is False
    with pytest.raises(adapter.BrowserUseUnavailable):
        asyncio.run(adapter.run_hosted_task(task="synthetic task"))


def test_v4_run_omits_model_and_enforces_cost_cap(monkeypatch):
    configured(monkeypatch)
    calls = []

    class Runs:
        def create(self, *args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(id="run-1")

        def wait_for_completion(self, run_id):
            assert run_id == "run-1"
            return SimpleNamespace(status="completed", output={"title": "Synthetic"})

    class Client:
        runs = Runs()

        def close(self):
            calls.append(("closed", {}))

    monkeypatch.setattr(adapter, "_new_client", lambda: Client())
    result = asyncio.run(adapter.run_hosted_task(task="Return a synthetic result."))
    assert result == {"run_id": "run-1", "status": "completed", "output": {"title": "Synthetic"}}
    assert calls[0] == (("Return a synthetic result.",), {"max_cost_usd": 1.0})
    assert calls[-1][0] == "closed"


@pytest.mark.parametrize("status", ["failed", "cancelled", "timed_out", "running"])
def test_non_success_status_is_rejected(monkeypatch, status):
    configured(monkeypatch)

    class Runs:
        def create(self, *args, **kwargs):
            return SimpleNamespace(id="run-1")

        def wait_for_completion(self, run_id):
            return SimpleNamespace(status=status, output="not accepted")

    monkeypatch.setattr(adapter, "_new_client", lambda: SimpleNamespace(runs=Runs()))
    with pytest.raises(adapter.BrowserUseRunError):
        asyncio.run(adapter.run_hosted_task(task="synthetic task"))


def test_missing_output_and_sdk_failures_are_safe(monkeypatch):
    configured(monkeypatch)

    class Runs:
        def create(self, *args, **kwargs):
            return SimpleNamespace(id="run-1")

        def wait_for_completion(self, run_id):
            return SimpleNamespace(status="completed")

    monkeypatch.setattr(adapter, "_new_client", lambda: SimpleNamespace(runs=Runs()))
    with pytest.raises(adapter.BrowserUseRunError, match="without a result"):
        asyncio.run(adapter.run_hosted_task(task="synthetic task"))

    class FailingRuns:
        def create(self, *args, **kwargs):
            raise RuntimeError("provider secret")

    monkeypatch.setattr(adapter, "_new_client", lambda: SimpleNamespace(runs=FailingRuns()))
    with pytest.raises(adapter.BrowserUseRunError, match="run failed") as error:
        asyncio.run(adapter.run_hosted_task(task="synthetic task"))
    assert "provider secret" not in str(error.value)


def test_empty_task_is_rejected_without_client_creation(monkeypatch):
    monkeypatch.setattr(adapter, "_new_client", lambda: pytest.fail("client must not be created"))
    with pytest.raises(adapter.BrowserUseRunError, match="non-empty"):
        asyncio.run(adapter.run_hosted_task(task="  "))
