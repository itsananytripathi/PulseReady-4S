from sqlalchemy import func, select

from app.models import AuditLog, Simulation
from conftest import auth


def test_protected_routes_reject_missing_and_invalid_api_keys(api):
    client, _, _ = api
    requests = [
        lambda headers: client.post("/api/v1/ingest", headers=headers, files={
            "file": ("signals.json", b"[]", "application/json"),
        }),
        lambda headers: client.get("/api/v1/overview", headers=headers),
        lambda headers: client.get("/api/v1/audit/verify", headers=headers),
        lambda headers: client.post("/api/v1/simulate", headers=headers, json={
            "facility_code": "A-01", "baseline_demand_beds": 10,
        }),
        lambda headers: client.post("/api/v1/alerts/missing/review", headers=headers, json={
            "decision": "acknowledged", "officer_id": "security-test",
        }),
    ]
    for request in requests:
        missing = request({})
        invalid = request(auth("invalid-key"))
        assert missing.status_code == 401
        assert invalid.status_code == 401
        assert "invalid-key" not in invalid.text


def test_oversized_upload_is_rejected_without_persistence(api):
    client, Session, _ = api
    response = client.post(
        "/api/v1/ingest",
        headers=auth(),
        files={"file": ("oversized.json", b"x" * 2_000_001, "application/json")},
    )
    assert response.status_code == 413
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_invalid_simulation_payload_does_not_persist_simulation_or_audit(api):
    client, Session, _ = api
    response = client.post("/api/v1/simulate", headers=auth(), json={
        "facility_code": "A-01", "baseline_demand_beds": "not-an-integer",
    })
    assert response.status_code == 422
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Simulation)) == 0
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 0
