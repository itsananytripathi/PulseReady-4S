from __future__ import annotations
import io, json, math
import uuid
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pandas as pd
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import Base, engine, get_db
from app.config import settings
from app.models import Tenant, Facility, HealthSignal, Alert, ReadinessMetric, Simulation
from app.schemas import (
    IngestSummary, OverviewOut, ReadinessOut, AlertOut,
    SimulateRequest, SimulateResponse, AlertReviewRequest, AlertReviewResponse,
    AuditVerifyResponse, IntegrationStatusOut
)
from app.security import current_tenant
from app.analytics import rolling_baseline_anomalies, calculate_4s_readiness
from app.audit import append_audit, verify_audit_chain
from app.integrations.external_clients import integration_statuses
from app.simulation.service import run_capacity_simulation
from app.routers.briefings import router as briefings_router

app = FastAPI(
    title="PulseReady 4S API",
    version="0.1.0",
    description="Synthetic-data operational readiness prototype. Not a clinical or outbreak-prediction system."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.include_router(briefings_router)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

def utc_now():
    return datetime.now(timezone.utc)

def _parse_timestamp(value) -> datetime:
    ts = pd.to_datetime(value, utc=True, errors="raise").to_pydatetime()
    return ts

@app.get("/healthz")
def healthz():
    return {"status": "ok", "mode": "synthetic-demo"}

@app.get("/api/v1/integrations/status", response_model=list[IntegrationStatusOut])
def integration_status(tenant: Tenant = Depends(current_tenant)):
    """Return non-secret integration diagnostics for an authenticated tenant."""
    return integration_statuses()

@app.post("/api/v1/ingest", response_model=IngestSummary)
async def ingest(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(current_tenant),
):
    filename = (file.filename or "").lower()
    if not (filename.endswith(".csv") or filename.endswith(".json")):
        raise HTTPException(415, "Upload a .csv or .json file")
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, "Upload exceeds configured size limit")
    try:
        if filename.endswith(".csv"):
            frame = pd.read_csv(io.BytesIO(raw))
        else:
            obj = json.loads(raw.decode("utf-8"))
            if isinstance(obj, dict):
                obj = obj.get("records")
            if not isinstance(obj, list):
                raise ValueError("JSON must be a list of records or {'records': [...]}")
            frame = pd.DataFrame(obj)
    except Exception as exc:
        raise HTTPException(400, f"Could not parse upload: {exc}") from exc

    required = {"facility_code", "signal_type", "observed_at", "value"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise HTTPException(422, {"message": "Missing required columns", "missing": missing})
    if frame.empty:
        return IngestSummary(accepted_rows=0, rejected_rows=0, rejected=[], created_signal_ids=[], alerts_created=0)

    # Validate row-by-row; malformed rows are rejected, valid rows continue.
    accepted = []
    rejected = []
    now = utc_now()
    for idx, row in frame.iterrows():
        row_number = int(idx) + 2 if filename.endswith(".csv") else int(idx) + 1
        try:
            facility_code = str(row["facility_code"]).strip()
            signal_type = str(row["signal_type"]).strip()
            if not facility_code or facility_code.lower() == "nan":
                raise ValueError("facility_code is required")
            if not signal_type or signal_type.lower() == "nan":
                raise ValueError("signal_type is required")
            value = float(row["value"])
            if not math.isfinite(value) or value < 0:
                raise ValueError("value must be a finite non-negative number")
            observed_at = _parse_timestamp(row["observed_at"])
            if observed_at < now - timedelta(hours=settings.max_signal_age_hours):
                raise ValueError("observed_at exceeds allowed freshness window")
            if observed_at > now + timedelta(minutes=settings.max_future_skew_minutes):
                raise ValueError("observed_at is too far in the future")
            facility = db.scalar(select(Facility).where(
                Facility.tenant_id == tenant.id,
                Facility.facility_code == facility_code,
                Facility.is_active.is_(True)
            ))
            if facility is None:
                raise ValueError("unknown facility_code for this tenant")
            accepted.append({
                "row_number": row_number, "facility": facility,
                "signal_type": signal_type, "value": value, "observed_at": observed_at,
                "unit": str(row.get("unit", "count")) if pd.notna(row.get("unit", "count")) else "count",
                "source": str(row.get("source", "synthetic")) if pd.notna(row.get("source", "synthetic")) else "synthetic",
            })
        except Exception as exc:
            rejected.append({"row_number": row_number, "reason": str(exc)})

    created_ids, alerts_created = [], 0
    # Baselines computed only within each facility/signal type, against prior stored rows.
    for group_key in {(r["facility"].id, r["signal_type"]) for r in accepted}:
        facility_id, signal_type = group_key
        prior_rows = db.scalars(select(HealthSignal).where(
            HealthSignal.tenant_id == tenant.id,
            HealthSignal.facility_id == facility_id,
            HealthSignal.signal_type == signal_type
        ).order_by(HealthSignal.observed_at.asc()).limit(1000)).all()
        group_new = sorted(
            [r for r in accepted if r["facility"].id == facility_id and r["signal_type"] == signal_type],
            key=lambda r: r["observed_at"]
        )
        history = [{"observed_at": s.observed_at, "value": s.value} for s in prior_rows]
        history.extend([{"observed_at": r["observed_at"], "value": r["value"]} for r in group_new])
        flags = rolling_baseline_anomalies(pd.DataFrame(history), window=7, min_periods=4) if len(history) >= 5 else None
        flag_by_time = {}
        if flags is not None:
            # Timestamps are unique only if the source data makes them unique; map by row order/time.
            for _, frow in flags.iterrows():
                flag_by_time[pd.Timestamp(frow["observed_at"]).to_pydatetime()] = (
                    bool(frow["is_anomaly"]), None if pd.isna(frow["anomaly_score"]) else float(frow["anomaly_score"])
                )
        for r in group_new:
            is_anomaly, score = flag_by_time.get(r["observed_at"], (False, None))
            signal = HealthSignal(
                tenant_id=tenant.id, facility_id=facility_id, signal_type=signal_type,
                observed_at=r["observed_at"], value=r["value"], unit=r["unit"], source=r["source"],
                is_anomaly=is_anomaly, anomaly_score=score
            )
            db.add(signal)
            db.flush()
            created_ids.append(signal.id)
            if is_anomaly:
                db.add(Alert(
                    tenant_id=tenant.id, facility_id=facility_id, signal_id=signal.id,
                    alert_type="statistical_anomaly", severity="review", status="open",
                    title=f"Unusual {signal_type} signal",
                    explanation=f"Observed value {r['value']} exceeded the configured rolling-baseline threshold. Verify source quality and context; this is not a confirmed outbreak."
                ))
                alerts_created += 1
    append_audit(
        db, tenant_id=tenant.id, actor_id="api-key",
        action="signals.ingested", entity_type="ingest_batch", entity_id=str(uuid4()),
        payload={"accepted_rows": len(accepted), "rejected_rows": len(rejected), "alerts_created": alerts_created}
    )
    db.commit()
    return IngestSummary(
        accepted_rows=len(accepted), rejected_rows=len(rejected), rejected=rejected,
        created_signal_ids=created_ids, alerts_created=alerts_created
    )

@app.get("/api/v1/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_db), tenant: Tenant = Depends(current_tenant)):
    facilities = db.scalars(select(Facility).where(
        Facility.tenant_id == tenant.id, Facility.is_active.is_(True)
    ).order_by(Facility.facility_code)).all()
    readiness = []
    for f in facilities:
        calc = calculate_4s_readiness(
            staff_available=f.staff_available, staff_required=f.staff_required,
            supply_on_hand=f.supply_on_hand, daily_supply_consumption=f.daily_supply_consumption,
            staffed_beds=f.staffed_beds, total_beds=f.total_beds,
            system_status_score=f.system_status_score
        )
        # Persist a snapshot each time overview is requested; acceptable for demo, move to explicit job in production.
        metric = ReadinessMetric(
            tenant_id=tenant.id, facility_id=f.id, measured_at=utc_now(),
            staff_score=calc["staff_score"], stuff_score=calc["stuff_score"],
            space_score=calc["space_score"], system_score=calc["system_score"],
            overall_score=calc["overall_score"], formula_version="4s-v1"
        )
        db.add(metric)
        readiness.append(ReadinessOut(
            facility_id=f.id, facility_code=f.facility_code, facility_name=f.name,
            staff_score=calc["staff_score"], stuff_score=calc["stuff_score"],
            space_score=calc["space_score"], system_score=calc["system_score"],
            overall_score=calc["overall_score"], supply_buffer_days=calc["supply_buffer_days"],
            supply_status=calc["supply_status"], staffed_beds=f.staffed_beds, total_beds=f.total_beds
        ))
    alerts = db.execute(select(Alert, Facility.facility_code).join(
        Facility, Alert.facility_id == Facility.id
    ).where(
        Alert.tenant_id == tenant.id, Facility.tenant_id == tenant.id, Alert.status == "open"
    ).order_by(Alert.created_at.desc()).limit(100)).all()
    alert_out = [
        AlertOut(
            id=a.id, facility_id=a.facility_id, facility_code=code,
            severity=a.severity, status=a.status, title=a.title,
            explanation=a.explanation, created_at=a.created_at
        ) for a, code in alerts
    ]
    db.commit()
    return OverviewOut(generated_at=utc_now(), readiness=readiness, active_alerts=alert_out)

@app.get("/api/v1/audit/verify", response_model=AuditVerifyResponse)
def verify_audit(db: Session = Depends(get_db), tenant: Tenant = Depends(current_tenant)):
    return verify_audit_chain(db, tenant.id)

@app.post("/api/v1/simulate", response_model=SimulateResponse)
def simulate(payload: SimulateRequest, db: Session = Depends(get_db), tenant: Tenant = Depends(current_tenant)):
    facility = db.scalar(select(Facility).where(
        Facility.tenant_id == tenant.id, Facility.facility_code == payload.facility_code,
        Facility.is_active.is_(True)
    ))
    if facility is None:
        raise HTTPException(404, "Facility not found for this tenant")
    result = run_capacity_simulation(
        staffed_beds=facility.staffed_beds, total_beds=facility.total_beds,
        baseline_demand_beds=payload.baseline_demand_beds,
        demand_uplift_pct=payload.demand_uplift_pct, absenteeism_pct=payload.absenteeism_pct
    ).model_dump(exclude={"model_version", "seed", "horizon_hours"})
    simulation_id = str(uuid.uuid4())
    row = Simulation(
        id=simulation_id, tenant_id=tenant.id, facility_id=facility.id,
        demand_uplift_pct=payload.demand_uplift_pct, absenteeism_pct=payload.absenteeism_pct,
        baseline_staffed_beds=facility.staffed_beds,
        simulated_staffed_beds=result["simulated_staffed_beds"],
        projected_demand_beds=result["projected_demand_beds"],
        shortfall_beds=result["shortfall_beds"]
    )
    db.add(row)
    append_audit(
        db, tenant_id=tenant.id, actor_id="api-key", action="simulation.created",
        entity_type="simulation", entity_id=simulation_id,
        payload={"facility_code": facility.facility_code, "demand_uplift_pct": payload.demand_uplift_pct,
                 "absenteeism_pct": payload.absenteeism_pct, **result}
    )
    db.commit()
    return SimulateResponse(
        simulation_id=row.id, facility_code=facility.facility_code,
        baseline_staffed_beds=facility.staffed_beds,
        simulated_staffed_beds=result["simulated_staffed_beds"],
        projected_demand_beds=result["projected_demand_beds"],
        shortfall_beds=result["shortfall_beds"],
        capacity_utilization_pct=result["capacity_utilization_pct"]
    )

@app.post("/api/v1/alerts/{alert_id}/review", response_model=AlertReviewResponse)
def review_alert(
    alert_id: str, payload: AlertReviewRequest,
    db: Session = Depends(get_db), tenant: Tenant = Depends(current_tenant)
):
    alert = db.scalar(select(Alert).where(Alert.id == alert_id, Alert.tenant_id == tenant.id))
    if alert is None:
        # Avoid leaking whether another tenant owns this alert.
        raise HTTPException(404, "Alert not found")
    if alert.status != "open":
        raise HTTPException(409, f"Alert is already {alert.status}")
    now = utc_now()
    old_status = alert.status
    alert.status = payload.decision
    alert.reviewed_at = now
    alert.reviewed_by = payload.officer_id
    alert.review_decision = payload.decision
    alert.review_note = payload.note
    audit = append_audit(
        db, tenant_id=tenant.id, actor_id=payload.officer_id,
        action="alert.reviewed", entity_type="alert", entity_id=alert.id,
        payload={"from_status": old_status, "to_status": payload.decision, "note": payload.note}
    )
    db.commit()
    return AlertReviewResponse(
        alert_id=alert.id, status=alert.status, reviewed_at=now, audit_entry_hash=audit.entry_hash
    )
