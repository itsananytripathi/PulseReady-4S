"""Deterministic end-to-end smoke coverage for the synthetic demo workflow.

The application exposes no audit-chain verifier endpoint or helper. This test
recomputes the existing canonical SHA-256 entries locally and asserts the
stored previous-hash links without changing the production audit design.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Alert, AuditLog, HealthSignal, Simulation
from conftest import TENANT_A, auth, json_bytes


def _assert_audit_chain(entries):
    ordered = sorted(entries, key=lambda entry: (entry.created_at, entry.id))
    previous_hash = None
    for entry in ordered:
        assert entry.previous_hash == previous_hash, (
            f"audit chain link mismatch for {entry.action}/{entry.entity_id}"
        )
        canonical = json.dumps({
            "tenant_id": entry.tenant_id,
            "actor_id": entry.actor_id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "payload": json.loads(entry.payload_json),
            "previous_hash": entry.previous_hash,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert entry.entry_hash == hashlib.sha256(canonical.encode("utf-8")).hexdigest(), (
            f"audit hash mismatch for {entry.action}/{entry.entity_id}"
        )
        previous_hash = entry.entry_hash


def test_end_to_end_smoke_ingest_overview_simulation_and_review(api):
    client, Session, _ = api
    base_time = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    records = [
        {
            "facility_code": "A-01",
            "signal_type": "respiratory_symptom_reports",
            "observed_at": (base_time + timedelta(minutes=index)).isoformat(),
            "value": value,
            "unit": "count",
            "source": "e2e-smoke",
        }
        for index, value in enumerate([5, 5, 5, 5, 5, 5, 5, 30])
    ]

    ingested = client.post(
        "/api/v1/ingest",
        headers=auth(),
        files={"file": ("e2e_smoke.json", json_bytes({"records": records}), "application/json")},
    )
    assert ingested.status_code == 200, ingested.text
    ingestion_body = ingested.json()
    assert ingestion_body["accepted_rows"] == 8
    assert ingestion_body["rejected_rows"] == 0
    assert len(ingestion_body["created_signal_ids"]) == 8
    assert ingestion_body["alerts_created"] == 1

    with Session() as db:
        signals = db.scalars(
            select(HealthSignal).where(
                HealthSignal.tenant_id == TENANT_A,
                HealthSignal.signal_type == "respiratory_symptom_reports",
            ).order_by(HealthSignal.observed_at)
        ).all()
        assert len(signals) == 8
        assert sum(signal.is_anomaly for signal in signals) == 1
        alert = db.scalar(select(Alert).where(Alert.tenant_id == TENANT_A))
        assert alert is not None
        alert_id = alert.id
        assert alert.status == "open"

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
    assert len(overview_body["active_alerts"]) == 1
    assert overview_body["active_alerts"][0]["id"] == alert_id

    simulated = client.post(
        "/api/v1/simulate",
        headers=auth(),
        json={
            "facility_code": "A-01",
            "baseline_demand_beds": 70,
            "demand_uplift_pct": 10,
            "absenteeism_pct": 25,
        },
    )
    assert simulated.status_code == 200, simulated.text
    simulation_body = simulated.json()
    simulation_id = simulation_body["simulation_id"]
    assert simulation_body["facility_code"] == "A-01"
    assert simulation_body["baseline_staffed_beds"] == 80
    assert simulation_body["simulated_staffed_beds"] == 60
    assert simulation_body["projected_demand_beds"] == 77
    assert simulation_body["shortfall_beds"] == 17
    assert simulation_body["capacity_utilization_pct"] == 128.33

    with Session() as db:
        simulation = db.get(Simulation, simulation_id)
        assert simulation is not None
        assert simulation.tenant_id == TENANT_A
        assert simulation.simulated_staffed_beds == 60
        simulation_audit = db.scalar(select(AuditLog).where(
            AuditLog.tenant_id == TENANT_A,
            AuditLog.action == "simulation.created",
            AuditLog.entity_id == simulation_id,
        ))
        assert simulation_audit is not None
        assert simulation_audit.entity_type == "simulation"

    reviewed = client.post(
        f"/api/v1/alerts/{alert_id}/review",
        headers=auth(),
        json={
            "decision": "acknowledged",
            "note": "Reviewed deterministic smoke-test alert",
            "officer_id": "e2e-smoke-officer",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    review_body = reviewed.json()
    assert review_body["alert_id"] == alert_id
    assert review_body["status"] == "acknowledged"
    assert len(review_body["audit_entry_hash"]) == 64

    verified = client.get("/api/v1/audit/verify", headers=auth())
    assert verified.status_code == 200, verified.text
    assert verified.json() == {
        "valid": True,
        "checked_count": 3,
        "first_invalid_event_id": None,
        "failure_reason": None,
    }

    with Session() as db:
        reviewed_alert = db.get(Alert, alert_id)
        assert reviewed_alert is not None
        assert reviewed_alert.status == "acknowledged"
        audit_entries = db.scalars(select(AuditLog).where(
            AuditLog.tenant_id == TENANT_A
        )).all()
        assert {entry.action for entry in audit_entries} == {
            "signals.ingested", "simulation.created", "alert.reviewed"
        }
        _assert_audit_chain(audit_entries)
