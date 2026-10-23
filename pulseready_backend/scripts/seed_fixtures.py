"""Safely seed the six approved synthetic fixtures through the real API path."""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


FIXTURE_TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
FIXTURE_TENANT_NAME = "Synthetic Fixture Tenant"
FIXTURE_FACILITY_ID = "fixture-facility-a"
FIXTURE_KEY = "fixture-seed-key"
FIXTURE_FACILITY = {
    "facility_code": "A-01",
    "name": "Synthetic Fixture Hospital",
    "total_beds": 100,
    "staffed_beds": 80,
    "staff_available": 80,
    "staff_required": 80,
    "supply_on_hand": 700,
    "daily_supply_consumption": 100,
    "system_status_score": 90,
}


def parse_timestamp(value):
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be an ISO-8601 string") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def sqlite_path(database_url):
    if not database_url.startswith("sqlite:///") or database_url.endswith(":memory:"):
        raise ValueError("seed target must be a file-backed SQLite URL")
    path = Path(database_url[len("sqlite:///"):]).expanduser().resolve()
    if path.name.lower() == "pulseready.db":
        raise ValueError("refusing to seed the normal pulseready.db database")
    if path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
        raise ValueError("seed target must use a SQLite database filename")
    return path


def load_and_validate_fixtures(fixture_dir):
    manifest_path = fixture_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    scenarios = manifest.get("scenarios")
    if manifest.get("synthetic_data") is not True or not isinstance(scenarios, list):
        raise ValueError("manifest must declare synthetic_data and a scenarios list")
    required_ids = {
        "baseline_normal", "staffing_shortage", "supply_buffer_low",
        "bed_surge", "stale_telemetry", "combined_stress",
    }
    if {scenario.get("scenario_id") for scenario in scenarios} != required_ids:
        raise ValueError("manifest must contain exactly the six approved scenario IDs")
    loaded = []
    for scenario in scenarios:
        filename = scenario.get("filename", "")
        path = (fixture_dir / filename).resolve()
        if path.parent != fixture_dir.resolve() or path.name != filename:
            raise ValueError(f"fixture path is outside the approved directory: {filename}")
        payload = json.loads(path.read_text())
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list) or not records:
            raise ValueError(f"{filename} must contain a non-empty records list")
        seen = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"{filename} contains a non-object record")
            missing = {"facility_code", "signal_type", "observed_at", "value"} - set(record)
            if missing:
                raise ValueError(f"{filename} is missing required fields: {sorted(missing)}")
            if record["facility_code"] != FIXTURE_FACILITY["facility_code"]:
                raise ValueError(f"{filename} contains an unprovisioned facility")
            if not str(record["signal_type"]).strip():
                raise ValueError(f"{filename} contains an empty signal_type")
            value = record["value"]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"{filename} contains an invalid value")
            timestamp = parse_timestamp(record["observed_at"])
            unit = record.get("unit", "count")
            source = record.get("source", "synthetic")
            if not str(source).startswith("fixture:"):
                raise ValueError(f"{filename} must use a fixture source label")
            key = (record["signal_type"], timestamp, float(value), str(unit), str(source))
            if key in seen:
                raise ValueError(f"{filename} contains duplicate natural-key records")
            seen.add(key)
        loaded.append((scenario, payload))
    return manifest, loaded


def signal_key(record):
    return (
        record.signal_type,
        parse_timestamp(record.observed_at),
        float(record.value),
        record.unit,
        record.source,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", required=True,
        help="explicit file-backed SQLite URL, never the normal pulseready.db",
    )
    parser.add_argument(
        "--fixtures-dir", type=Path,
        default=Path(__file__).parents[1] / "fixtures",
        help="approved fixture directory (defaults to pulseready_backend/fixtures)",
    )
    args = parser.parse_args(argv)
    target = sqlite_path(args.database_url)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest, loaded = load_and_validate_fixtures(args.fixtures_dir.resolve())
    as_of = parse_timestamp(manifest["as_of"])

    os.environ["DATABASE_URL"] = args.database_url
    os.environ["PULSEREADY_API_KEYS"] = json.dumps({FIXTURE_KEY: FIXTURE_TENANT_ID})
    sys.path.insert(0, str(Path(__file__).parents[1]))

    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app import main as application
    from app.db import Base, SessionLocal, engine
    from app.models import Facility, HealthSignal, Tenant

    application.utc_now = lambda: as_of
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        tenant = db.get(Tenant, FIXTURE_TENANT_ID)
        if tenant is None:
            db.add(Tenant(id=FIXTURE_TENANT_ID, name=FIXTURE_TENANT_NAME))
        elif tenant.name != FIXTURE_TENANT_NAME:
            raise ValueError("target tenant exists with unexpected fixture identity")
        facility = db.scalar(select(Facility).where(
            Facility.tenant_id == FIXTURE_TENANT_ID,
            Facility.facility_code == FIXTURE_FACILITY["facility_code"],
        ))
        if facility is None:
            db.add(Facility(id=FIXTURE_FACILITY_ID, tenant_id=FIXTURE_TENANT_ID, **FIXTURE_FACILITY))
        elif any(getattr(facility, field) != value for field, value in FIXTURE_FACILITY.items()):
            raise ValueError("target facility exists with unexpected fixture identity")
        db.commit()

    with SessionLocal() as db:
        existing = {
            signal_key(signal)
            for signal in db.scalars(select(HealthSignal).where(
                HealthSignal.tenant_id == FIXTURE_TENANT_ID,
                HealthSignal.facility_id == FIXTURE_FACILITY_ID,
            )).all()
        }

    pending = []
    for scenario, payload in loaded:
        expected = scenario["expected_observable_behavior"]
        records = payload["records"]
        if expected["accepted_rows"] == 0:
            pending.append((scenario, "skipped_expected_rejection", payload))
            continue
        keys = {
            (record["signal_type"], parse_timestamp(record["observed_at"]), float(record["value"]),
             str(record.get("unit", "count")), str(record.get("source", "synthetic")))
            for record in records
        }
        present = keys & existing
        if present and present != keys:
            raise ValueError(f"{scenario['scenario_id']} is partially seeded; refusing unsafe completion")
        pending.append((scenario, "already_present" if present == keys else "insert", payload))

    inserted = 0
    already_present = 0
    skipped = 0
    with TestClient(application.app) as client:
        for scenario, state, payload in pending:
            scenario_id = scenario["scenario_id"]
            if state == "skipped_expected_rejection":
                skipped += 1
                print(f"{scenario_id}: skipped (fixture is expected to be rejected by freshness policy)")
                continue
            if state == "already_present":
                already_present += 1
                print(f"{scenario_id}: already_present")
                continue
            response = client.post(
                "/api/v1/ingest",
                headers={"X-API-Key": FIXTURE_KEY},
                files={"file": (scenario["filename"], json.dumps(payload).encode(), "application/json")},
            )
            if response.status_code != 200:
                raise RuntimeError(f"{scenario_id}: ingestion failed with HTTP {response.status_code}")
            body = response.json()
            expected = scenario["expected_observable_behavior"]
            if any(body[field] != expected[field] for field in ("accepted_rows", "rejected_rows", "alerts_created")):
                raise RuntimeError(f"{scenario_id}: ingestion result did not match manifest")
            inserted += body["accepted_rows"]
            existing.update({
                (record["signal_type"], parse_timestamp(record["observed_at"]), float(record["value"]),
                 str(record.get("unit", "count")), str(record.get("source", "synthetic")))
                for record in payload["records"]
            })
            print(f"{scenario_id}: inserted {body['accepted_rows']} signals, {body['alerts_created']} alerts")

    print(f"target={target}")
    print(f"summary: inserted={inserted} already_present={already_present} skipped={skipped} failed=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
