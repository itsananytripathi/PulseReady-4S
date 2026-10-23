# PulseReady 4S — Backend Foundation (H0–H6)

A modular FastAPI + SQLAlchemy scaffold for a **synthetic-data hackathon demo**:
ingest → validate → anomaly flag → 4S readiness/buffer → what-if simulation → human review/audit.

This is a production-minded starting point, **not a production-certified system**. Do not upload patient-identifiable or real hospital data.

## 1. Run locally

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Export the env vars in .env into your shell; Python does not auto-load .env.
export DATABASE_URL='sqlite:///./pulseready.db'
export PULSEREADY_API_KEYS='{"demo-key-change-me":"11111111-1111-4111-8111-111111111111"}'
python -m app.seed_demo
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Send `X-API-Key: demo-key-change-me` on protected endpoints.

## 1a. Run the isolated tests

From `pulseready_backend/`, run:

```bash
pytest -q
```

The integration fixture creates a fresh SQLite database under pytest's temporary directory for every test. It does not use `pulseready.db` or the configured development database.

## 1b. Run the end-to-end smoke test

From `pulseready_backend/` with the project virtual environment at the outer root:

```bash
../.venv/bin/python -m pytest -v tests/test_e2e_smoke.py
```

The smoke test exercises ingestion, anomaly alert creation, overview readiness and supply-buffer fields, simulation persistence and audit linkage, and alert review through the real FastAPI application. It uses the existing per-test isolated SQLite fixture under pytest's temporary directory, never touches `pulseready.db`, makes no network calls, and keeps the test API key in memory. The API now exposes the read-only `/api/v1/audit/verify` verifier; the smoke test also recomputes the stored SHA-256 links locally and reports any mismatch as a failed test.

## 2. PostgreSQL

Create a database/user, then set:

```bash
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/pulseready'
```

Run `python -m app.seed_demo` and start Uvicorn. `create_all()` is convenient for a demo only. Use Alembic migrations for controlled schema evolution before any real deployment.

## 3. API quick test

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/ingest' \
  -H 'X-API-Key: demo-key-change-me' \
  -F 'file=@sample_signals.csv'

curl 'http://127.0.0.1:8000/api/v1/overview' \
  -H 'X-API-Key: demo-key-change-me'

curl -X POST 'http://127.0.0.1:8000/api/v1/simulate' \
  -H 'Content-Type: application/json' -H 'X-API-Key: demo-key-change-me' \
  -d '{"facility_code":"DEMO-HOSP-01","demand_uplift_pct":25,"absenteeism_pct":15,"baseline_demand_beds":80}'
```

Review an alert by ID returned from `/api/v1/overview`:

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/alerts/ALERT_ID/review' \
  -H 'Content-Type: application/json' -H 'X-API-Key: demo-key-change-me' \
  -d '{"decision":"acknowledged","note":"Reviewed against synthetic source feed","officer_id":"demo-officer-01"}'
```

## 3a. Frontend integration status

No frontend application, dashboard source tree, package manifest, or mock-data client is present in this repository. Therefore no dashboard element is currently connected to live API responses, and no frontend mock can be claimed as complete. The backend surfaces ready for a future dashboard are:

- `GET /healthz` — unauthenticated service health.
- `POST /api/v1/ingest` — authenticated signal ingestion and anomaly summary.
- `GET /api/v1/overview` — authenticated 4S readiness, supply-buffer fields, and active alerts.
- `POST /api/v1/simulate` — authenticated deterministic what-if results.
- `POST /api/v1/alerts/{alert_id}/review` — authenticated human review transition.

The generated FastAPI `/docs` page is the only current interactive client. Frontend cards, charts, alert workflows, API error/loading states, and live refresh behavior remain unimplemented.

## 3b. Frozen backend contract inventory

All protected routes require the existing `X-API-Key` header. The key maps to a tenant through `PULSEREADY_API_KEYS`; every facility, signal, alert, simulation, readiness snapshot, and audit query is scoped to that tenant.

| Method and path | Authentication | Request | Success response | Important status codes | Persistence and scope |
|---|---|---|---|---|---|
| `GET /healthz` | None | None | `{"status":"ok","mode":"synthetic-demo"}` | `200` | Read-only; no tenant scope. |
| `POST /api/v1/ingest` | `X-API-Key` | Multipart `file`; `.csv` or `.json` list/`{"records": [...]}` with required `facility_code`, `signal_type`, `observed_at`, `value`; optional `unit`, `source`. | `IngestSummary`: accepted/rejected counts, created signal IDs, alerts created, note. | `200`, `400` parse, `401` auth, `413` size, `415` extension, `422` missing columns/upload validation. | Persists accepted `HealthSignal`, rule-generated `Alert`, and `signals.ingested` `AuditLog`; all tenant-scoped; commits once after processing. |
| `GET /api/v1/overview` | `X-API-Key` | None | `OverviewOut`: `generated_at`, `readiness[]`, `active_alerts[]`; readiness includes all four 4S scores, supply buffer/status, staffed and total beds. | `200`, `401` auth. | Reads tenant facilities/alerts and persists a `ReadinessMetric` snapshot for each facility; commits; no cross-tenant rows are returned. |
| `POST /api/v1/simulate` | `X-API-Key` | `SimulateRequest`: `facility_code`, `baseline_demand_beds`, optional `demand_uplift_pct` 0–500 and `absenteeism_pct` 0–100. | `SimulateResponse`: simulation ID, baseline/effective beds, projected demand, shortfall, utilization, note. | `200`, `401` auth, `404` facility outside tenant, `422` schema. | Persists `Simulation` and `simulation.created` `AuditLog` using the same ID; commits; tenant-scoped. |
| `POST /api/v1/alerts/{alert_id}/review` | `X-API-Key` | `AlertReviewRequest`: decision `acknowledged|dismissed|escalated`, officer ID, optional note. | `AlertReviewResponse`: alert ID, new status, reviewed time, audit hash. | `200`, `401` auth, `404` missing/foreign alert, `409` already reviewed, `422` schema. | Updates the tenant alert and appends `alert.reviewed` audit event in one commit. |
| `GET /api/v1/audit/verify` | `X-API-Key` | None | `AuditVerifyResponse`: `valid`, `checked_count`, `first_invalid_event_id`, `failure_reason`. Corruption is a successful `200` with `valid: false`. | `200`, `401` auth, `500` verifier/database failure. | Read-only complete chain verification for the authorized tenant; no commit or repair. |

Verifier failure reasons are `event_hash_mismatch`, `previous_hash_mismatch`, `invalid_genesis`, and `malformed_event`. An empty tenant chain is valid with `checked_count: 0`. The audit model has no sequence column, so sequence-gap and duplicate-sequence checks are not applicable. The writer canonicalizes the object `{tenant_id, actor_id, action, entity_type, entity_id, payload, previous_hash}` with `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, encodes UTF-8, and hashes with SHA-256. Genesis uses `previous_hash = null`; subsequent events use the prior event selected by `created_at DESC, id DESC`. Verification walks the same convention in ascending `created_at, id` order. It detects altered payloads, integrity metadata, hashes, genesis, broken predecessor links, malformed payloads, and visible forks. It cannot prove that a privileged database administrator did not delete the entire history, delete the tail, or rewrite all rows and hashes consistently. Concurrent appends are not database-serialized and can fork; verification reports the visible break but does not prevent it.

## 4. Input contract

CSV or JSON array / `{"records":[...]}`. Required fields:

- `facility_code`: provisioned facility within the authenticated tenant
- `signal_type`: non-empty metric identifier
- `observed_at`: ISO-8601 timestamp with timezone recommended
- `value`: finite, non-negative number

Optional: `unit`, `source`. Rows older than `MAX_SIGNAL_AGE_HOURS` or too far in the future are rejected. Malformed rows are rejected individually; missing required columns rejects the whole file.

## 5. Important design choices / limitations

- **Tenant isolation:** API key resolves to a tenant; every facility/signal/alert/simulation query includes that tenant scope. This is not a substitute for PostgreSQL Row-Level Security (RLS), production identity, per-user authorization, or security testing.
- **Demo authentication:** API keys are configured in environment JSON and are not a complete key-management system. Use a secret manager, rotation, rate limits, TLS, and user/role authorization in real deployments.
- **Anomaly detection:** rolling z-score uses prior observations only; first observations may have no baseline. It flags unusual synthetic operational signals for human verification—not outbreaks or diagnoses. The threshold and constant-baseline fallback are prototype heuristics.
- **4S scores:** transparent equal-weight v1 heuristic, not clinically validated. “Stuff” uses a 7-day supply target as a prototype assumption.
- **Simulation:** deterministic arithmetic only; not an epidemiological forecast or bed-allocation recommendation.
- **Audit:** append-only at the application layer with a SHA-256 previous-hash chain and a tenant-scoped read-only verifier at `/api/v1/audit/verify`. This is **tamper-evident only under controlled write access**, not inherently immutable against a privileged database administrator. For stronger guarantees, add restricted DB roles/triggers, external signed checkpoints or WORM storage, and independent verification.
- **Audit concurrency:** chain-head selection and insertion are not serialized by a database lock in this demo. Concurrent transactions can race on the same previous hash and require production database constraints/serialization plus an external verifier before relying on ordering or completeness.
- **Readiness snapshots:** `/overview` writes a snapshot on each request to make the demo history visible. In production, separate read endpoints from scheduled snapshot jobs.
- **FHIR/HL7:** no live hospital integration is implemented here. Any future adapter is a synthetic standards-based ingestion specification until tested and authorized against a specific source system.
- **Compliance:** compliance-oriented architecture only. No HIPAA/DPDP certification or legal-compliance claim is made.

## 5a. Synthetic fixtures and safe seeding

The versioned synthetic scenarios are under `fixtures/` with metadata in `fixtures/manifest.json`: `baseline_normal`, `staffing_shortage`, `supply_buffer_low`, `bed_surge`, `stale_telemetry`, and `combined_stress`. Freshness tests use the manifest's fixed `as_of` time; the stale scenario is intentionally rejected by the normal 72-hour policy. The current anomaly engine detects positive deviations only, so staffing and supply scenarios use explicit positive `staff_shortage` and `supply_risk` signals. These alerts do not rewrite the facility's static 4S fields because no telemetry-to-facility mapping exists.

Use a separate file-backed SQLite target; the command refuses `pulseready.db`:

```bash
TARGET_DIR="$(mktemp -d)"
../.venv/bin/python scripts/seed_fixtures.py \
  --database-url "sqlite:///$TARGET_DIR/fixture-seed.sqlite3"
```

The seeder prevalidates all six files, inserts accepted rows through `/api/v1/ingest`, generates alerts through the existing anomaly path, skips the intentionally rejected stale scenario, and uses natural keys to make a second run non-duplicating. It prints inserted, already-present, skipped, and failed counts. It never truncates or resets a database.

## 5b. Local synthetic FHIR R4 coverage

`app/fhir.py` builds and locally checks synthetic FHIR R4 `Location`, `Observation`, and `SupplyDelivery` resources. The Observation uses the official R4 heart-rate example semantics (LOINC `8867-4` with UCUM `/min`); SupplyDelivery uses the R4 `device` supply type, a synthetic item code system, a UCUM `{box}` quantity, and a Location destination. Tests cover required fields, resource types, references, code/unit consistency, and invalid payload rejection. This is a focused shape/semantic validator, not full FHIR profile, terminology, or conformance validation; no remote server or validator dependency is required.

## 5c. External adapter boundary

The repository contains no weather, public-health, geospatial, LLM, or other external API adapter. Core ingestion, overview, simulation, review, and audit behavior therefore has no network dependency. No unnecessary live integration was added.

## 5d. Security verification scope

Tests cover missing/invalid API keys on protected endpoints, tenant-scoped overview/simulation/review/audit access, malformed and non-finite signal values, stale/future timestamps, unknown facilities, oversized uploads, invalid simulation payloads, audit read-only behavior, and safe isolated seeding. There is no database-level RLS, production key rotation/rate limiting, CORS policy, external audit anchoring, or concurrency serialization; these remain deployment controls rather than verified claims of this demo.

## 6. Suggested H0–H6 build order

H0–H1: configure DB and tenant/facility seed.  
H1–H2: validate CSV/JSON and freshness.  
H2–H3: persist accepted signals and rejected-row reasons.  
H3–H4: anomaly baseline + review alerts.  
H4–H5: 4S/buffer overview.  
H5–H6: deterministic simulation, audit, smoke-test demo.

## 7. Before real deployment

Use migrations, PostgreSQL RLS and tenant-scoped DB policies; test authorization boundaries; add request IDs and idempotency keys; add rate limits, TLS, secret rotation, backups and restore drills; add external audit anchoring; validate data contracts and retention; and complete privacy, security, contractual, clinical-safety and jurisdictional reviews as appropriate.
