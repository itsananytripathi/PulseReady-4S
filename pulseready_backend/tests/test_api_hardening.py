import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Alert, AuditLog, HealthSignal, Simulation
from conftest import KEY_B, TENANT_A, auth, json_bytes, record


def upload(client, body, filename="signals.json", content_type="application/json", key=None):
    return client.post(
        "/api/v1/ingest", headers=auth(key) if key else auth(),
        files={"file": (filename, body, content_type)},
    )


def test_successful_csv_ingestion_is_persisted(api):
    client, Session, _ = api
    rows = [record(value=12), record(value=14, signal_type="staff_absence")]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    response = upload(client, output.getvalue().encode(), "signals.csv", "text/csv")
    assert response.status_code == 200, response.text
    assert response.json()["accepted_rows"] == 2
    with Session() as db:
        assert db.scalar(select(HealthSignal).where(HealthSignal.tenant_id == TENANT_A)) is not None


def test_successful_json_ingestion_supports_records_wrapper(api):
    client, _, _ = api
    response = upload(client, json_bytes({"records": [record(value=9)]}))
    assert response.status_code == 200, response.text
    assert response.json()["accepted_rows"] == 1


def test_missing_columns_rejects_whole_upload_and_malformed_rows_are_reported(api):
    client, _, _ = api
    missing = upload(client, json_bytes([{"facility_code": "A-01"}]))
    assert missing.status_code == 422
    assert "Missing required columns" in missing.text

    mixed = upload(client, json_bytes([record(value=4), record(value="not-a-number")]))
    assert mixed.status_code == 200
    assert mixed.json()["accepted_rows"] == 1
    assert mixed.json()["rejected_rows"] == 1
    assert "could not convert" in mixed.json()["rejected"][0]["reason"].lower()


@pytest.mark.parametrize("observed_at, reason", [
    (datetime.now(timezone.utc) - timedelta(hours=73), "allowed freshness"),
    (datetime.now(timezone.utc) + timedelta(minutes=11), "too far in the future"),
])
def test_stale_and_future_timestamps_are_rejected(api, observed_at, reason):
    client, _, _ = api
    response = upload(client, json_bytes([record(observed_at=observed_at.isoformat())]))
    assert response.status_code == 200
    assert response.json()["accepted_rows"] == 0
    assert reason in response.json()["rejected"][0]["reason"]


@pytest.mark.parametrize("value", [-1, "NaN", "Infinity", "-Infinity"])
def test_negative_and_nonfinite_values_are_rejected(api, value):
    client, _, _ = api
    response = upload(client, json_bytes([record(value=value)]))
    assert response.status_code == 200
    assert response.json()["accepted_rows"] == 0
    assert "finite non-negative" in response.json()["rejected"][0]["reason"]


def test_unknown_facility_code_is_rejected_without_cross_tenant_lookup(api):
    client, _, _ = api
    response = upload(client, json_bytes([record(facility_code="B-01")]))
    assert response.status_code == 200
    assert response.json()["accepted_rows"] == 0
    assert "unknown facility_code" in response.json()["rejected"][0]["reason"]


def test_overview_is_tenant_scoped(api):
    client, _, _ = api
    response = client.get("/api/v1/overview", headers=auth())
    assert response.status_code == 200
    assert [row["facility_code"] for row in response.json()["readiness"]] == ["A-01"]
    assert "B-01" not in response.text
    other = client.get("/api/v1/overview", headers=auth(KEY_B))
    assert [row["facility_code"] for row in other.json()["readiness"]] == ["B-01"]
    assert "A-01" not in other.text


@pytest.mark.parametrize("absenteeism, expected_capacity, expected_utilization", [
    (0, 80, 62.5),
    (100, 0, None),
])
def test_simulation_is_deterministic_and_handles_zero_capacity(api, absenteeism, expected_capacity, expected_utilization):
    client, Session, _ = api
    payload = {"facility_code": "A-01", "baseline_demand_beds": 50, "demand_uplift_pct": 0, "absenteeism_pct": absenteeism}
    first = client.post("/api/v1/simulate", headers=auth(), json=payload)
    second = client.post("/api/v1/simulate", headers=auth(), json=payload)
    assert first.status_code == second.status_code == 200
    for response in (first, second):
        body = response.json()
        assert body["simulated_staffed_beds"] == expected_capacity
        assert body["capacity_utilization_pct"] == expected_utilization
    assert first.json()["projected_demand_beds"] == second.json()["projected_demand_beds"]
    with Session() as db:
        assert db.scalar(select(Simulation).where(Simulation.tenant_id == TENANT_A)) is not None


def test_other_tenant_cannot_simulate_or_review_a_foreign_alert(api):
    client, Session, _ = api
    assert client.post("/api/v1/simulate", headers=auth(KEY_B), json={
        "facility_code": "A-01", "baseline_demand_beds": 10,
    }).status_code == 404

    with Session() as db:
        alert = Alert(
            id="alert-a", tenant_id=TENANT_A, facility_id="facility-a", alert_type="test",
            severity="review", status="open", title="Synthetic alert", explanation="Test only",
        )
        db.add(alert)
        db.commit()
    response = client.post("/api/v1/alerts/alert-a/review", headers=auth(KEY_B), json={
        "decision": "acknowledged", "officer_id": "tenant-b-officer",
    })
    assert response.status_code == 404


def test_alert_review_rejects_repeated_review_and_records_audit_chain(api):
    client, Session, _ = api
    with Session() as db:
        db.add_all([
            Alert(
                id="alert-review", tenant_id=TENANT_A, facility_id="facility-a", alert_type="test",
                severity="review", status="open", title="Synthetic alert", explanation="Test only",
            ),
            Alert(
                id="alert-review-2", tenant_id=TENANT_A, facility_id="facility-a", alert_type="test",
                severity="review", status="open", title="Synthetic alert 2", explanation="Test only",
            ),
        ])
        db.commit()

    reviewed = client.post("/api/v1/alerts/alert-review/review", headers=auth(), json={
        "decision": "dismissed", "note": "Reviewed synthetic fixture", "officer_id": "officer-a",
    })
    assert reviewed.status_code == 200, reviewed.text
    repeated = client.post("/api/v1/alerts/alert-review/review", headers=auth(), json={
        "decision": "acknowledged", "officer_id": "officer-a",
    })
    assert repeated.status_code == 409
    second = client.post("/api/v1/alerts/alert-review-2/review", headers=auth(), json={
        "decision": "acknowledged", "note": "Second synthetic review", "officer_id": "officer-a",
    })
    assert second.status_code == 200

    with Session() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.entity_id == "alert-review"))
        assert audit is not None
        assert audit.actor_id == "officer-a"
        assert audit.entity_type == "alert"
        assert audit.action == "alert.reviewed"
        assert audit.created_at is not None
        assert audit.entry_hash and len(audit.entry_hash) == 64
        payload = json.loads(audit.payload_json)
        assert payload["to_status"] == "dismissed"
        chain = db.scalars(select(AuditLog).where(AuditLog.tenant_id == TENANT_A).order_by(AuditLog.created_at, AuditLog.id)).all()
        assert len(chain) == 2
        assert all(entry.previous_hash == (chain[i - 1].entry_hash if i else None) for i, entry in enumerate(chain))
        for entry in chain:
            canonical = json.dumps({
                "tenant_id": entry.tenant_id, "actor_id": entry.actor_id, "action": entry.action,
                "entity_type": entry.entity_type, "entity_id": entry.entity_id,
                "payload": json.loads(entry.payload_json), "previous_hash": entry.previous_hash,
            }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            assert entry.entry_hash == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
