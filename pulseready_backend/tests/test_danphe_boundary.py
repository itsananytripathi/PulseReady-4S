from datetime import datetime, timezone

import pytest

from app import config
from app.integrations import danphe
from app.integrations.danphe import (
    DanpheIntegrationUnavailable,
    DanpheOperationalDataProvider,
    OperationalSignal,
    SyntheticOperationalDataProvider,
    get_operational_data_provider,
)


def test_synthetic_provider_is_deterministic_and_normalizes_source_data():
    provider = SyntheticOperationalDataProvider([{
        "facility_code": "DEMO-HOSP-01",
        "signal_type": "staff_on_duty",
        "observed_at": "2026-10-25T00:00:00+05:45",
        "value": 12,
    }])
    result = provider.fetch_signals(facility_code="DEMO-HOSP-01")
    assert result.source_kind == "synthetic"
    assert result.signals[0].observed_at == datetime(2026, 10, 24, 18, 15, tzinfo=timezone.utc)
    assert result.signals[0].source == "synthetic"


def test_operational_signal_rejects_naive_and_negative_values():
    with pytest.raises(ValueError):
        OperationalSignal(
            facility_code="DEMO-HOSP-01",
            signal_type="beds",
            observed_at="2026-10-25T00:00:00",
            value=1,
        )
    with pytest.raises(ValueError):
        OperationalSignal(
            facility_code="DEMO-HOSP-01",
            signal_type="beds",
            observed_at="2026-10-25T00:00:00+00:00",
            value=-1,
        )


def test_danphe_provider_is_disabled_without_database_access(monkeypatch):
    monkeypatch.setattr(danphe, "settings", config.Settings(
        database_url="sqlite:///:memory:",
        api_keys={"test": "tenant"},
        max_upload_bytes=100,
        max_signal_age_hours=72,
        max_future_skew_minutes=10,
        danphe_enabled=False,
    ))
    with pytest.raises(DanpheIntegrationUnavailable, match="disabled"):
        DanpheOperationalDataProvider()


def test_enabled_danphe_provider_requires_approved_view_and_never_guesses_schema(monkeypatch):
    monkeypatch.setattr(danphe, "settings", config.Settings(
        database_url="sqlite:///:memory:",
        api_keys={"test": "tenant"},
        max_upload_bytes=100,
        max_signal_age_hours=72,
        max_future_skew_minutes=10,
        danphe_enabled=True,
        danphe_connection_string="synthetic-read-only-connection",
        danphe_approved_view=None,
    ))
    with pytest.raises(DanpheIntegrationUnavailable, match="approved operational view"):
        DanpheOperationalDataProvider()


def test_default_provider_is_synthetic_when_danphe_disabled(monkeypatch):
    monkeypatch.setattr(danphe, "settings", config.Settings(
        database_url="sqlite:///:memory:",
        api_keys={"test": "tenant"},
        max_upload_bytes=100,
        max_signal_age_hours=72,
        max_future_skew_minutes=10,
        danphe_enabled=False,
    ))
    assert isinstance(get_operational_data_provider(), SyntheticOperationalDataProvider)
