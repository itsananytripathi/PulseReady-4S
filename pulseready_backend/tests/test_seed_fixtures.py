import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Alert, Facility, HealthSignal, Tenant


BACKEND_DIR = Path(__file__).parents[1]
SEED_SCRIPT = BACKEND_DIR / "scripts" / "seed_fixtures.py"


def run_seed(db_path, fixture_dir=None):
    command = [sys.executable, str(SEED_SCRIPT), "--database-url", f"sqlite:///{db_path}"]
    if fixture_dir is not None:
        command.extend(["--fixtures-dir", str(fixture_dir)])
    return subprocess.run(command, cwd=BACKEND_DIR, capture_output=True, text=True)


def setup_database(db_path):
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(Tenant(id="other-tenant", name="Unrelated Tenant"))
        db.add(Facility(
            id="other-facility", tenant_id="other-tenant", facility_code="OTHER-01",
            name="Unrelated Hospital", total_beds=10, staffed_beds=5,
            staff_available=5, staff_required=5, supply_on_hand=50,
            daily_supply_consumption=10, system_status_score=50,
        ))
        db.add(HealthSignal(
            id="unrelated-signal", tenant_id="other-tenant", facility_id="other-facility",
            signal_type="occupancy", observed_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
            value=1, unit="count", source="unrelated-test",
        ))
        db.commit()
    return engine, Session


def counts(Session):
    with Session() as db:
        return {
            "signals": db.scalar(select(func.count()).select_from(HealthSignal)),
            "alerts": db.scalar(select(func.count()).select_from(Alert)),
            "tenants": db.scalar(select(func.count()).select_from(Tenant)),
            "other_signals": db.scalar(select(func.count()).select_from(HealthSignal).where(
                HealthSignal.tenant_id == "other-tenant"
            )),
        }


def test_fixture_seed_is_idempotent_and_preserves_unrelated_records(tmp_path):
    db_path = tmp_path / "fixture-seed.sqlite3"
    engine, Session = setup_database(db_path)
    before = counts(Session)

    first = run_seed(db_path)
    assert first.returncode == 0, first.stderr
    assert "summary: inserted=45 already_present=0 skipped=1 failed=0" in first.stdout
    after_first = counts(Session)
    assert after_first == {
        "signals": before["signals"] + 45,
        "alerts": 5,
        "tenants": before["tenants"] + 1,
        "other_signals": before["other_signals"],
    }

    second = run_seed(db_path)
    assert second.returncode == 0, second.stderr
    assert "summary: inserted=0 already_present=5 skipped=1 failed=0" in second.stdout
    assert counts(Session) == after_first
    engine.dispose()


def test_seed_refuses_normal_demo_database(tmp_path):
    result = run_seed(tmp_path / "pulseready.db")
    assert result.returncode != 0
    assert "refusing to seed the normal pulseready.db database" in result.stderr


def test_malformed_fixture_fails_before_database_writes(tmp_path):
    fixture_copy = tmp_path / "fixtures"
    shutil.copytree(BACKEND_DIR / "fixtures", fixture_copy)
    malformed_path = fixture_copy / "baseline_normal.json"
    malformed = json.loads(malformed_path.read_text())
    malformed["records"][0].pop("value")
    malformed_path.write_text(json.dumps(malformed))
    db_path = tmp_path / "malformed.sqlite3"

    result = run_seed(db_path, fixture_copy)
    assert result.returncode != 0
    assert "missing required fields" in result.stderr
    assert not db_path.exists()
