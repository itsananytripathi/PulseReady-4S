from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import append_audit
from app.config import settings
from app.db import get_db
from app.integrations.adaption_adapter import AdaptionUnavailable, review_operational_summary
from app.integrations.external_clients import ExternalProviderError, IntegrationUnavailable, live_call_allowed
from app.integrations.elevenlabs_adapter import synthesize_speech
from app.models import Alert, Tenant
from app.schemas import AudioBriefingRequest, SummaryReviewRequest, SummaryReviewResponse
from app.security import current_tenant


router = APIRouter(prefix="/api/v1")
LOCAL_AUDIO_PATH = Path(__file__).resolve().parents[1] / "assets" / "demo_briefing.mp3"


def _authorized_alert(alert_id: str, db: Session, tenant: Tenant) -> Alert:
    alert = db.scalar(select(Alert).where(Alert.id == alert_id, Alert.tenant_id == tenant.id))
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _has_human_approval(alert: Alert) -> bool:
    """Map the existing persisted acknowledged state to approval for audio."""
    return (
        alert.status == "acknowledged"
        and alert.review_decision == "acknowledged"
        and bool(alert.reviewed_by)
        and alert.reviewed_at is not None
    )


@router.post("/review/summary", response_model=SummaryReviewResponse)
async def review_summary(
    payload: SummaryReviewRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(current_tenant),
):
    alert = _authorized_alert(payload.alert_id, db, tenant)
    try:
        result = await review_operational_summary(
            alert_id=alert.id,
            summary=alert.explanation,
            evidence=[alert.explanation],
        )
    except AdaptionUnavailable as exc:
        raise HTTPException(status_code=503, detail="Adaption summary review is not currently available.") from exc

    append_audit(
        db,
        tenant_id=tenant.id,
        actor_id="api-key",
        action="briefing.summary_reviewed",
        entity_type="alert",
        entity_id=alert.id,
        payload={
            "provider": result.get("provider"),
            "mode": result.get("mode"),
            "review_status": result.get("review_status"),
            "approved": result.get("approved"),
        },
    )
    db.commit()
    return SummaryReviewResponse(alert_id=alert.id, **result)


@router.post("/briefings/audio")
async def briefing_audio(
    payload: AudioBriefingRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(current_tenant),
):
    alert = _authorized_alert(payload.alert_id, db, tenant)
    if not _has_human_approval(alert):
        raise HTTPException(status_code=409, detail="A persisted acknowledged alert review is required.")

    if settings.integration_mode == "live":
        if not getattr(settings, "elevenlabs_voice_id", None) or not live_call_allowed("elevenlabs"):
            raise HTTPException(status_code=503, detail="Live ElevenLabs audio is not configured.")
        try:
            audio = await synthesize_speech(text=alert.explanation)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Briefing text is not valid for audio generation.") from exc
        except (IntegrationUnavailable, ExternalProviderError) as exc:
            raise HTTPException(status_code=503, detail="Live ElevenLabs audio is unavailable.") from exc
        append_audit(
            db,
            tenant_id=tenant.id,
            actor_id="api-key",
            action="briefing.audio_generated",
            entity_type="alert",
            entity_id=alert.id,
            payload={"provider": "elevenlabs", "mode": "live"},
        )
        db.commit()
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store", "X-PulseReady-Integration": "elevenlabs-live"},
        )

    try:
        audio = LOCAL_AUDIO_PATH.read_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Local synthetic demo audio is unavailable; place a valid MP3 at app/assets/demo_briefing.mp3.",
        ) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Local synthetic demo audio could not be read.") from exc

    append_audit(
        db,
        tenant_id=tenant.id,
        actor_id="api-key",
        action="briefing.audio_served",
        entity_type="alert",
        entity_id=alert.id,
        payload={"provider": "local-cache", "mode": "mock"},
    )
    db.commit()
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-PulseReady-Integration": "mock-local-cache"},
    )
