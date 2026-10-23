import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.config import settings as configured_settings
from app.db import Base, get_db
from app.models import Facility, Tenant


TENANT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
KEY_A = "tenant-a-test-key"
KEY_B = "tenant-b-test-key"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    """Use a per-test SQLite file; never bind tests to the developer database."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'isolated.sqlite3'}",
        connect_args={"check_same_thread": False},
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    db = TestSession()
    db.add_all([
        Tenant(id=TENANT_A, name="Synthetic Tenant A"),
        Tenant(id=TENANT_B, name="Synthetic Tenant B"),
        Facility(
            id="facility-a", tenant_id=TENANT_A, facility_code="A-01", name="Tenant A Hospital",
            total_beds=100, staffed_beds=80, staff_available=80, staff_required=80,
            supply_on_hand=700, daily_supply_consumption=100, system_status_score=90,
        ),
        Facility(
            id="facility-b", tenant_id=TENANT_B, facility_code="B-01", name="Tenant B Hospital",
            total_beds=60, staffed_beds=30, staff_available=30, staff_required=40,
            supply_on_hand=200, daily_supply_consumption=100, system_status_score=70,
        ),
    ])
    db.commit()
    db.close()

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(main, "settings", configured_settings.__class__(
        database_url=f"sqlite:///{tmp_path / 'isolated.sqlite3'}",
        api_keys={KEY_A: TENANT_A, KEY_B: TENANT_B},
        max_upload_bytes=2_000_000,
        max_signal_age_hours=72,
        max_future_skew_minutes=10,
    ))
    monkeypatch.setattr("app.security.settings", main.settings)
    main.app.dependency_overrides[get_db] = override_db
    client = TestClient(main.app)
    try:
        yield client, TestSession, engine
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def auth(key=KEY_A):
    return {"X-API-Key": key}


def record(value=10, facility_code="A-01", observed_at=None, signal_type="occupancy"):
    return {
        "facility_code": facility_code,
        "signal_type": signal_type,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "value": value,
    }


def json_bytes(records):
    return json.dumps(records).encode()
