import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app import main
from app.models import Alert, AuditLog, HealthSignal
from conftest import TENANT_A, auth, json_bytes


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text())
FIXED_NOW = datetime.fromisoformat(MANIFEST["as_of"].replace("Z", "+00:00"))


@pytest.mark.parametrize(
    "scenario",
    MANIFEST["scenarios"],
    ids=[scenario["scenario_id"] for scenario in MANIFEST["scenarios"]],
)
def test_synthetic_fixture_uses_real_ingestion_analytics_and_overview(scenario, api, monkeypatch):
    client, Session, _ = api
    monkeypatch.setattr(main, "utc_now", lambda: FIXED_NOW)
    payload = json.loads((FIXTURE_DIR / scenario["filename"]).read_text())
    records = payload["records"]
    expected = scenario["expected_observable_behavior"]

    response = client.post(
        "/api/v1/ingest",
        headers=auth(),
        files={
            "file": (
                scenario["filename"],
                json_bytes(payload),
                "application/json",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_rows"] == expected["accepted_rows"]
    assert body["rejected_rows"] == expected["rejected_rows"]
    assert body["alerts_created"] == expected["alerts_created"]
    if "rejection_reason_contains" in expected:
        assert expected["rejection_reason_contains"] in body["rejected"][0]["reason"]

    overview = client.get("/api/v1/overview", headers=auth())
    assert overview.status_code == 200, overview.text
    overview_body = overview.json()
    assert len(overview_body["readiness"]) == 1
    readiness = overview_body["readiness"][0]
    assert readiness["facility_code"] == "A-01"
    assert readiness["staff_score"] == 100.0
    assert readiness["stuff_score"] == 100.0
    assert readiness["space_score"] == 80.0
    assert readiness["system_score"] == 90.0
    assert readiness["overall_score"] == 92.5
    assert readiness["supply_buffer_days"] == 7.0
    assert readiness["supply_status"] == "adequate"
    assert len(overview_body["active_alerts"]) == expected["alerts_created"]
    assert all(alert["severity"] == expected.get("alert_severity", "review")
               for alert in overview_body["active_alerts"])

    with Session() as db:
        stored_signals = db.scalars(select(HealthSignal).where(
            HealthSignal.tenant_id == TENANT_A
        )).all()
        stored_alerts = db.scalars(select(Alert).where(
            Alert.tenant_id == TENANT_A
        )).all()
        audit_entries = db.scalars(select(AuditLog).where(
            AuditLog.tenant_id == TENANT_A
        )).all()
        assert len(stored_signals) == expected["accepted_rows"]
        assert len(stored_alerts) == expected["alerts_created"]
        assert len(audit_entries) == 1
        assert audit_entries[0].action == "signals.ingested"
        assert len(records) >= expected["accepted_rows"]
