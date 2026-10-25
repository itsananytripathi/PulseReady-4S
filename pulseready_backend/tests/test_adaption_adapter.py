import asyncio
import os
from types import SimpleNamespace

import pytest

from app.integrations import adaption_adapter as adapter


def configured(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "settings",
        SimpleNamespace(
            enabled_integrations=("adaption_labs",),
            adaption_labs_api_key="synthetic-adaption-key",
            adaption_labs_endpoint="https://synthetic.example",
            external_http_timeout_seconds=3.0,
        ),
    )


def test_disabled_and_missing_credentials_fail_closed(monkeypatch):
    monkeypatch.setattr(adapter, "settings", SimpleNamespace(enabled_integrations=(), adaption_labs_api_key=None, adaption_labs_endpoint=None, external_http_timeout_seconds=3.0))
    assert adapter.is_configured() is False
    with pytest.raises(adapter.AdaptionUnavailable):
        adapter._new_client()

    configured(monkeypatch)
    monkeypatch.setattr(adapter.settings, "adaption_labs_api_key", "YOUR_API_KEY_HERE", raising=False)
    assert adapter.is_configured() is False
    with pytest.raises(adapter.AdaptionUnavailable):
        asyncio.run(adapter.run_dataset_adaptation(dataset_id="dataset-a", column_mapping={}, job_specification={}))


def test_sdk_import_and_initialization_failures_are_safe(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setitem(__import__("sys").modules, "adaption", None)
    with pytest.raises(adapter.AdaptionUnavailable, match="not installed"):
        adapter._new_client()

    class BrokenAdaption:
        def __init__(self, **kwargs):
            raise RuntimeError("secret-provider-detail")

    monkeypatch.setitem(__import__("sys").modules, "adaption", SimpleNamespace(Adaption=BrokenAdaption))
    with pytest.raises(adapter.AdaptionUnavailable, match="Could not initialize") as error:
        adapter._new_client()
    assert "secret-provider-detail" not in str(error.value)


def test_estimate_validates_response_and_never_requires_network(monkeypatch):
    configured(monkeypatch)

    class Datasets:
        def adapt(self, *args, **kwargs):
            assert kwargs["estimate"] is True
            return SimpleNamespace(estimated_credits_consumed=1.5)

    monkeypatch.setattr(adapter, "_new_client", lambda: SimpleNamespace(datasets=Datasets()))
    result = asyncio.run(adapter.run_dataset_adaptation(dataset_id="dataset-a", column_mapping={}, job_specification={}))
    assert result == {"mode": "estimate", "dataset_id": "dataset-a", "estimated_credits_consumed": 1.5}

    class InvalidDatasets(Datasets):
        def adapt(self, *args, **kwargs):
            return SimpleNamespace(estimated_credits_consumed="invalid")

    monkeypatch.setattr(adapter, "_new_client", lambda: SimpleNamespace(datasets=InvalidDatasets()))
    with pytest.raises(adapter.AdaptionJobError, match="invalid estimate"):
        asyncio.run(adapter.run_dataset_adaptation(dataset_id="dataset-a", column_mapping={}, job_specification={}))


def test_job_completion_success_failure_and_invalid_status(monkeypatch):
    configured(monkeypatch)

    class Datasets:
        def __init__(self, status):
            self.status = status

        def adapt(self, *args, **kwargs):
            return SimpleNamespace(run_id="run-a")

        def wait_for_completion(self, *args, **kwargs):
            return SimpleNamespace(status=self.status)

    monkeypatch.setattr(adapter, "_new_client", lambda: SimpleNamespace(datasets=Datasets("succeeded")))
    assert asyncio.run(adapter.run_dataset_adaptation(dataset_id="dataset-a", column_mapping={}, job_specification={}, estimate_only=False))["status"] == "succeeded"

    for status, expected in (("failed", "dataset job failed"), ("pending", "completed job status"), ("unknown", "invalid status")):
        monkeypatch.setattr(adapter, "_new_client", lambda status=status: SimpleNamespace(datasets=Datasets(status)))
        with pytest.raises(adapter.AdaptionJobError, match=expected):
            asyncio.run(adapter.run_dataset_adaptation(dataset_id="dataset-a", column_mapping={}, job_specification={}, estimate_only=False))


def test_timeout_and_sdk_errors_are_controlled(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("ADAPTION_JOB_TIMEOUT_SECONDS", "not-an-integer")
    with pytest.raises(adapter.AdaptionUnavailable, match="must be an integer"):
        asyncio.run(adapter.run_dataset_adaptation(dataset_id="dataset-a", column_mapping={}, job_specification={}))

    monkeypatch.setenv("ADAPTION_JOB_TIMEOUT_SECONDS", "1")
    monkeypatch.setattr(adapter, "_new_client", lambda: SimpleNamespace(datasets=SimpleNamespace(adapt=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider-secret")))))
    with pytest.raises(adapter.AdaptionJobError, match="dataset operation failed") as error:
        asyncio.run(adapter.run_dataset_adaptation(dataset_id="dataset-a", column_mapping={}, job_specification={}))
    assert "provider-secret" not in str(error.value)
    monkeypatch.delenv("ADAPTION_JOB_TIMEOUT_SECONDS", raising=False)


def test_invalid_dataset_and_summary_review_are_explicitly_unavailable(monkeypatch):
    configured(monkeypatch)
    with pytest.raises(adapter.AdaptionUnavailable, match="verified dataset ID"):
        asyncio.run(adapter.run_dataset_adaptation(dataset_id="YOUR_DATASET_ID", column_mapping={}, job_specification={}))
    with pytest.raises(adapter.AdaptionUnavailable, match="Single-summary review is not implemented"):
        asyncio.run(adapter.review_operational_summary(alert_id="alert-a", summary="synthetic", evidence=[]))
