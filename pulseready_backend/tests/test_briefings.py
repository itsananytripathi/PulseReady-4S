import json
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select

from app.audit import verify_audit_chain
from app.integrations import adaption_adapter
from app.models import Alert, AuditLog
from app.routers import briefings

KEY_A = "tenant-a-test-key"
KEY_B = "tenant-b-test-key"
TENANT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _add_alert(Session, *, alert_id="briefing-alert", tenant_id=TENANT_A, status="open"):
    with Session() as db:
        db.add(Alert(
            id=alert_id,
            tenant_id=tenant_id,
            facility_id="facility-a" if tenant_id == TENANT_A else "facility-b",
            alert_type="test",
            severity="review",
            status=status,
            title="Synthetic briefing alert",
            explanation="Synthetic operational evidence for human review.",
            reviewed_at=datetime.now(timezone.utc) if status == "acknowledged" else None,
            reviewed_by="demo-officer" if status == "acknowledged" else None,
            review_decision="acknowledged" if status == "acknowledged" else None,
        ))
        db.commit()


def test_mock_summary_review_is_labelled_and_audited(api):
    client, Session, _ = api
    _add_alert(Session)
    response = client.post("/api/v1/review/summary", headers={"X-API-Key": KEY_A}, json={"alert_id": "briefing-alert"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "mock"
    assert body["mode"] == "mock"
    assert body["review_status"] == "simulated"
    assert body["approved"] is False
    assert "no real Adaption review" in body["issues"][0]

    with Session() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "briefing.summary_reviewed"))
        assert audit is not None
        assert json.loads(audit.payload_json)["provider"] == "mock"
        assert verify_audit_chain(db, TENANT_A)["valid"] is True


def test_summary_review_is_tenant_scoped(api):
    client, Session, _ = api
    _add_alert(Session)
    response = client.post("/api/v1/review/summary", headers={"X-API-Key": KEY_B}, json={"alert_id": "briefing-alert"})
    assert response.status_code == 404


def test_audio_requires_persisted_human_approval_and_missing_mp3_is_controlled(api):
    client, Session, _ = api
    _add_alert(Session)
    denied = client.post("/api/v1/briefings/audio", headers={"X-API-Key": KEY_A}, json={"alert_id": "briefing-alert"})
    assert denied.status_code == 409

    _add_alert(Session, alert_id="approved-alert", status="acknowledged")
    missing = client.post("/api/v1/briefings/audio", headers={"X-API-Key": KEY_A}, json={"alert_id": "approved-alert"})
    assert missing.status_code == 503
    assert "demo_briefing.mp3" in missing.json()["detail"]


def test_mock_audio_serves_synthetic_mp3_without_provider_call(api, tmp_path, monkeypatch):
    client, Session, _ = api
    _add_alert(Session, alert_id="approved-audio", status="acknowledged")
    # One deterministic MPEG Layer III frame; this remains test-only and is
    # not presented as a production briefing asset.
    sample = b"\xff\xfb\x90\x64" + b"\x00" * 413
    path = tmp_path / "demo_briefing.mp3"
    path.write_bytes(sample)
    monkeypatch.setattr(briefings, "LOCAL_AUDIO_PATH", path)
    response = client.post("/api/v1/briefings/audio", headers={"X-API-Key": KEY_A}, json={"alert_id": "approved-audio"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-pulseready-integration"] == "mock-local-cache"
    assert response.content == sample


def test_live_summary_review_fails_closed_without_supported_contract(monkeypatch):
    monkeypatch.setattr(
        adaption_adapter,
        "settings",
        SimpleNamespace(integration_mode="live"),
    )
    import asyncio
    import pytest

    with pytest.raises(adaption_adapter.AdaptionUnavailable, match="not implemented"):
        asyncio.run(adaption_adapter.review_operational_summary(alert_id="a", summary="synthetic", evidence=[]))
