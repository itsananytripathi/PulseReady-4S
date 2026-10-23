import json

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from app import main
from app.audit import append_audit
from app.models import AuditLog
from conftest import KEY_B, TENANT_A, auth


def add_audits(Session, tenant_id=TENANT_A, count=1):
    with Session() as db:
        entries = []
        for index in range(count):
            entries.append(append_audit(
                db,
                tenant_id=tenant_id,
                actor_id="audit-test",
                action=f"audit.test.{index}",
                entity_type="test",
                entity_id=f"entity-{index}",
                payload={"index": index},
            ))
        db.commit()
        return [entry.id for entry in entries]


def verify(client, key=None):
    headers = auth(key) if key else {}
    return client.get("/api/v1/audit/verify", headers=headers)


def test_empty_chain_is_valid(api):
    client, _, _ = api
    response = verify(client, key=auth()["X-API-Key"])
    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "checked_count": 0,
        "first_invalid_event_id": None,
        "failure_reason": None,
    }


def test_single_and_multi_event_chains_are_valid(api):
    client, Session, _ = api
    add_audits(Session, count=1)
    single = verify(client, key=auth()["X-API-Key"])
    assert single.status_code == 200
    assert single.json()["valid"] is True
    assert single.json()["checked_count"] == 1

    add_audits(Session, count=2)
    multi = verify(client, key=auth()["X-API-Key"])
    assert multi.status_code == 200
    assert multi.json()["valid"] is True
    assert multi.json()["checked_count"] == 3


def test_tampered_payload_is_detected(api):
    client, Session, _ = api
    event_id = add_audits(Session)[0]
    with Session() as db:
        db.execute(update(AuditLog).where(AuditLog.id == event_id).values(
            payload_json=json.dumps({"index": 999})
        ))
        db.commit()

    result = verify(client, key=auth()["X-API-Key"]).json()
    assert result == {
        "valid": False,
        "checked_count": 1,
        "first_invalid_event_id": event_id,
        "failure_reason": "event_hash_mismatch",
    }


def test_malformed_payload_and_stored_hash_are_detected(api):
    client, Session, _ = api
    event_id = add_audits(Session)[0]
    with Session() as db:
        db.execute(update(AuditLog).where(AuditLog.id == event_id).values(
            payload_json="{not-json"
        ))
        db.commit()
    malformed = verify(client, key=auth()["X-API-Key"]).json()
    assert malformed["valid"] is False
    assert malformed["failure_reason"] == "malformed_event"

    with Session() as db:
        db.execute(update(AuditLog).where(AuditLog.id == event_id).values(
            payload_json=json.dumps({"index": 0}), entry_hash="0" * 64
        ))
        db.commit()
    altered_hash = verify(client, key=auth()["X-API-Key"]).json()
    assert altered_hash["valid"] is False
    assert altered_hash["first_invalid_event_id"] == event_id
    assert altered_hash["failure_reason"] == "event_hash_mismatch"


def test_previous_hash_break_is_detected(api):
    client, Session, _ = api
    ids = add_audits(Session, count=2)
    with Session() as db:
        db.execute(update(AuditLog).where(AuditLog.id == ids[1]).values(
            previous_hash="f" * 64
        ))
        db.commit()
    broken = verify(client, key=auth()["X-API-Key"]).json()
    assert broken["valid"] is False
    assert broken["first_invalid_event_id"] == ids[1]
    assert broken["failure_reason"] == "previous_hash_mismatch"

def test_missing_predecessor_is_detected(api):
    client, Session, _ = api
    ids = add_audits(Session, count=3)
    with Session() as db:
        db.execute(delete(AuditLog).where(AuditLog.id == ids[1]))
        db.commit()
    missing = verify(client, key=auth()["X-API-Key"]).json()
    assert missing["valid"] is False
    assert missing["first_invalid_event_id"] == ids[2]
    assert missing["failure_reason"] == "previous_hash_mismatch"


def test_invalid_genesis_is_detected(api):
    client, Session, _ = api
    event_id = add_audits(Session)[0]
    with Session() as db:
        db.execute(update(AuditLog).where(AuditLog.id == event_id).values(
            previous_hash="0" * 64
        ))
        db.commit()
    result = verify(client, key=auth()["X-API-Key"]).json()
    assert result["valid"] is False
    assert result["first_invalid_event_id"] == event_id
    assert result["failure_reason"] == "invalid_genesis"


def test_verification_requires_authentication_and_is_tenant_scoped(api):
    client, Session, _ = api
    add_audits(Session, tenant_id=TENANT_A)
    assert verify(client).status_code == 401
    assert verify(client, key="invalid-key").status_code == 401

    other_tenant = verify(client, key=KEY_B)
    assert other_tenant.status_code == 200
    assert other_tenant.json() == {
        "valid": True,
        "checked_count": 0,
        "first_invalid_event_id": None,
        "failure_reason": None,
    }


def test_verification_is_read_only_repeatable_and_survives_client_reload(api):
    client, Session, _ = api
    add_audits(Session, count=2)
    with Session() as db:
        before = [
            (entry.id, entry.previous_hash, entry.entry_hash, entry.payload_json)
            for entry in db.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)).all()
        ]

    first = verify(client, key=auth()["X-API-Key"])
    second = verify(client, key=auth()["X-API-Key"])
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

    reloaded_client = TestClient(main.app)
    reloaded = verify(reloaded_client, key=auth()["X-API-Key"])
    assert reloaded.status_code == 200
    assert reloaded.json() == first.json()

    with Session() as db:
        after = [
            (entry.id, entry.previous_hash, entry.entry_hash, entry.payload_json)
            for entry in db.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)).all()
        ]
    assert after == before
