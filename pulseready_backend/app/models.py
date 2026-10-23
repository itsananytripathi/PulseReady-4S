from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    String, DateTime, Float, Integer, Boolean, ForeignKey, Index, Text,
    UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    facilities: Mapped[list["Facility"]] = relationship(back_populates="tenant")

class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (UniqueConstraint("tenant_id", "facility_code", name="uq_facility_tenant_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    facility_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_beds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    staffed_beds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    staff_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    staff_required: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    supply_on_hand: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    daily_supply_consumption: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    isolation_capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    system_status_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    tenant: Mapped["Tenant"] = relationship(back_populates="facilities")
    readiness_metrics: Mapped[list["ReadinessMetric"]] = relationship(back_populates="facility")
    __table_args__ = (
        UniqueConstraint("tenant_id", "facility_code", name="uq_facility_tenant_code"),
        CheckConstraint("total_beds >= 0 AND staffed_beds >= 0 AND staffed_beds <= total_beds", name="ck_beds"),
        CheckConstraint("staff_available >= 0 AND staff_required >= 0", name="ck_staff"),
        CheckConstraint("supply_on_hand >= 0 AND daily_supply_consumption >= 0", name="ck_supply"),
    )

class ReadinessMetric(Base):
    __tablename__ = "readiness_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="RESTRICT"), index=True, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    staff_score: Mapped[float] = mapped_column(Float, nullable=False)
    stuff_score: Mapped[float] = mapped_column(Float, nullable=False)
    space_score: Mapped[float] = mapped_column(Float, nullable=False)
    system_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(32), default="4s-v1", nullable=False)
    facility: Mapped["Facility"] = relationship(back_populates="readiness_metrics")
    __table_args__ = (
        CheckConstraint("staff_score BETWEEN 0 AND 100 AND stuff_score BETWEEN 0 AND 100 AND space_score BETWEEN 0 AND 100 AND system_score BETWEEN 0 AND 100 AND overall_score BETWEEN 0 AND 100", name="ck_readiness_range"),
    )

class HealthSignal(Base):
    __tablename__ = "health_signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="RESTRICT"), index=True, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="count", nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="synthetic", nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (
        Index("ix_signal_tenant_facility_type_time", "tenant_id", "facility_id", "signal_type", "observed_at"),
        CheckConstraint("value >= 0", name="ck_signal_nonnegative"),
    )

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="RESTRICT"), index=True, nullable=False)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("health_signals.id", ondelete="RESTRICT"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="review", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (CheckConstraint("severity IN ('info','review','urgent')", name="ck_alert_severity"),
                      CheckConstraint("status IN ('open','acknowledged','dismissed','escalated')", name="ck_alert_status"))

class Simulation(Base):
    __tablename__ = "simulations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="RESTRICT"), index=True, nullable=False)
    demand_uplift_pct: Mapped[float] = mapped_column(Float, nullable=False)
    absenteeism_pct: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_staffed_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    simulated_staffed_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_demand_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    shortfall_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (Index("ix_audit_tenant_created", "tenant_id", "created_at"),)
