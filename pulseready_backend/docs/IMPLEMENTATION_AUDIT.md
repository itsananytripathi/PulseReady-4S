# PulseReady 4S implementation audit

## Baseline and repository evidence

The backend is a FastAPI/SQLAlchemy modular monolith using SQLite by default and
`X-API-Key` tenant lookup from `PULSEREADY_API_KEYS`. The Phase 2 baseline is
62 passed, 0 failed, 0 skipped, and 0 errors using Python 3.14.8 in the backend
virtual environment. No supplied reference repositories or license files were
present in the workspace; no reference source was copied.

## Module and route inventory

`app/main.py` exposes `GET /healthz`, authenticated `POST /api/v1/ingest`,
`GET /api/v1/overview`, `POST /api/v1/simulate`,
`POST /api/v1/alerts/{alert_id}/review`, and the additive read-only
`GET /api/v1/audit/verify`. `app/analytics.py` contains deterministic rolling
anomaly and 4S calculations. `app/audit.py` writes and verifies the existing
SHA-256 chain. `app/fhir.py` provides a deliberately narrow synthetic R4 shape
validator. `app/db.py`, `models.py`, `config.py`, and `security.py` define the
database, tenant scope, and API-key behavior. Fixtures and scripts are under
`fixtures/` and `scripts/`; isolated API tests are under `tests/`.

## Feature status

P0 ingestion, row validation, freshness rejection, deterministic anomaly
detection, transparent 4S readiness, supply buffer, simulation arithmetic,
human alert review, audit writing, and tenant-scoped audit verification are
implemented and covered by the existing tests. The new bounded SimPy package
(`app/simulation/`) is additive and preserves the existing simulation response.

P1 synthetic FHIR resource checks and a constrained, repository-controlled
Observation/Patient mapping interpreter are implemented. They are not universal
FHIR R4 or terminology conformance validation. Evidence-linked AI explanations
and differential privacy are not implemented.

P2 geographic visualization and equipment-maintenance workflows are not present.
P3 consumer, pharmacy, and emergency-dispatch workflows remain deferred.

The fourteen-feature matrix is therefore: P0 ingestion, data quality,
freshness, anomaly detection, 4S readiness, deterministic simulation, and
human review/audit are implemented for the synthetic demo. Signal-to-surge
prioritization is partial: anomaly alerts carry facility, signal, severity, and
explanation evidence, but there is no separate surge-ranking endpoint or
calibrated priority model. P1 FHIR mapping is partial; evidence-linked AI
explanations and differential privacy are not implemented. P2 geographic
visualization and maintenance prediction are deferred; P3 consumer/pharmacy/
SOS workflows are explicitly deferred.

## Audit contract

The existing chain is unchanged. The writer canonicalizes
`tenant_id, actor_id, action, entity_type, entity_id, payload, previous_hash`
with `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`,
encodes UTF-8, and hashes with SHA-256. Genesis has `previous_hash = null`;
verification orders by `created_at, id`. No sequence column exists. The new
`app/merkle.py` is an optional in-memory checkpoint/proof primitive with
domain-separated SHA-256 leaves and nodes, duplicate-last odd-level handling,
and an empty root of `None`; it does not alter historical audit records or add a
persistent checkpoint table/API. `checkpoint_from_audit_entries` and
`verify_audit_inclusion` bind a proof back to persisted event content supplied
by the trusted database layer; callers must still decide where checkpoint
metadata is durably stored or externally anchored.

## Compatibility risks and unchanged behavior

The `/api/v1/simulate` route still returns the existing arithmetic fields and
persists the same ORM/audit records. The SimPy process is bounded, creates a
fresh environment per call, and does not mutate live readiness. FHIR mapping is
allowlisted and uses explicit paths/constants; it does not evaluate client
input as code. Existing audit ordering and hash formats remain unchanged.

Known deployment risks remain: application-level audit writes are not serialized
for concurrent writers, API keys lack production key management/rate limiting,
`create_all()` is demo-only, and no database-level RLS or external audit anchor
exists. These are not claimed as fixed by this change.
