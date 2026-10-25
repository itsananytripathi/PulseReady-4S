"""Disabled-by-default boundary for approved Danphe operational data.

This module deliberately does not open a database connection. The checked-in
Danphe source proves SQL Server-oriented storage, but it does not provide an
authorized development connection, approved view schema, or a safe field-level
contract for PulseReady. Until those are supplied, only the synthetic provider
is usable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from pydantic import BaseModel, Field, field_validator

from app.config import settings


class DanpheIntegrationUnavailable(RuntimeError):
    """Raised when the Danphe bridge is disabled or lacks an approved contract."""


class OperationalSignal(BaseModel):
    facility_code: str = Field(min_length=1, max_length=80)
    signal_type: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    value: float
    unit: str | None = Field(default=None, max_length=40)
    source: str = Field(default="synthetic", min_length=1, max_length=80)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("value")
    @classmethod
    def require_finite_value(cls, value: float) -> float:
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("value must be finite")
        if value < 0:
            raise ValueError("value must be non-negative")
        return value


class OperationalDataBatch(BaseModel):
    signals: list[OperationalSignal]
    source_kind: str
    retrieved_at: datetime
    freshness_status: str


class OperationalDataProvider(ABC):
    """Read-only provider contract consumed by future orchestration code."""

    @abstractmethod
    def fetch_signals(self, *, facility_code: str, limit: int = 100) -> OperationalDataBatch:
        raise NotImplementedError


@dataclass(frozen=True)
class SyntheticOperationalDataProvider(OperationalDataProvider):
    """Deterministic provider for local tests and synthetic rehearsals."""

    signals: tuple[OperationalSignal, ...] = ()

    def __init__(self, signals: Iterable[OperationalSignal | dict] = ()):
        object.__setattr__(self, "signals", tuple(
            signal if isinstance(signal, OperationalSignal) else OperationalSignal.model_validate(signal)
            for signal in signals
        ))

    def fetch_signals(self, *, facility_code: str, limit: int = 100) -> OperationalDataBatch:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        selected = tuple(signal for signal in self.signals if signal.facility_code == facility_code)[:limit]
        now = datetime.now(timezone.utc)
        return OperationalDataBatch(
            signals=list(selected),
            source_kind="synthetic",
            retrieved_at=now,
            freshness_status="synthetic",
        )


class DanpheOperationalDataProvider(OperationalDataProvider):
    """Fail-closed placeholder until Danphe's approved read contract exists."""

    def __init__(self) -> None:
        if not settings.danphe_enabled:
            raise DanpheIntegrationUnavailable("Danphe integration is disabled.")
        if not settings.danphe_connection_string:
            raise DanpheIntegrationUnavailable("Danphe read-only connection is not configured.")
        if not settings.danphe_approved_view:
            raise DanpheIntegrationUnavailable("Danphe approved operational view is not configured.")
        raise DanpheIntegrationUnavailable(
            "Danphe integration requires an administrator-approved view schema before database access is enabled."
        )

    def fetch_signals(self, *, facility_code: str, limit: int = 100) -> OperationalDataBatch:
        raise DanpheIntegrationUnavailable("Danphe integration is not enabled in this build.")


def get_operational_data_provider() -> OperationalDataProvider:
    """Return synthetic data by default; never infer live Danphe access."""
    if settings.danphe_enabled:
        return DanpheOperationalDataProvider()
    return SyntheticOperationalDataProvider()
