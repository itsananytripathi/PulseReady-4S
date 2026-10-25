# PulseReady 4S API contracts

This document describes the routes registered by the current FastAPI
application. It is derived from `app/main.py`, `app/schemas.py`, and the
runtime OpenAPI route inventory. The backend is a synthetic-data demo; do not
send real patient data.

## Authentication and tenant scope

Protected routes require `X-API-Key`. The key is looked up in the
`PULSEREADY_API_KEYS` JSON configuration and resolves to exactly one tenant.
Facility, signal, alert, simulation, readiness-snapshot, and audit queries are
scoped to that tenant. Missing or invalid keys return `401`; a configured key
whose tenant is absent returns `403`. The API key is never returned in a
response.

`GET /healthz`, `/docs`, `/redoc`, `/openapi.json`, and
`/docs/oauth2-redirect` are unauthenticated framework/health routes. The
interactive documentation routes are not application data APIs.

## Route inventory

### `GET /healthz`

Authentication: none. Tenant scope: none. Read-only.

Response `200`:

```json
{"status":"ok","mode":"synthetic-demo"}
```

### `POST /api/v1/ingest`

Authentication: `X-API-Key`. Tenant scope: facility lookup and all writes use
the authenticated tenant.

Request: multipart form field `file`. The filename must end in `.csv` or
`.json`. JSON is either a list of records or `{"records": [...]}`. Required
record fields are `facility_code`, `signal_type`, `observed_at`, and `value`.
Optional fields are `unit` and `source`.

Values must be finite and non-negative. Timestamps are checked against the
configured freshness and future-skew limits. Unknown facilities and malformed
rows are rejected per row; missing required columns, invalid file type, parse
failure, and oversized uploads reject the request.

Response `200` (`IngestSummary`):

```json
{
  "accepted_rows": 8,
  "rejected_rows": 0,
  "rejected": [],
  "created_signal_ids": ["signal-uuid"],
  "alerts_created": 1,
  "note": "Signals are operational indicators for human review, not confirmed outbreaks."
}
```

Runtime errors: `400` malformed upload/JSON, `401` auth, `413` upload too
large, `415` unsupported extension, `422` missing columns or request
validation. Accepted signals, rule-generated alerts, and one
`signals.ingested` audit event are committed together after processing.

### `GET /api/v1/overview`

Authentication: `X-API-Key`. Tenant scope: only active facilities and open
alerts belonging to the authenticated tenant are returned.

Response `200` (`OverviewOut`):

```json
{
  "generated_at": "2026-10-23T10:00:00Z",
  "readiness": [{
    "facility_id": "facility-uuid",
    "facility_code": "A-01",
    "facility_name": "Tenant A Hospital",
    "staff_score": 100.0,
    "stuff_score": 100.0,
    "space_score": 80.0,
    "system_score": 90.0,
    "overall_score": 92.5,
    "supply_buffer_days": 7.0,
    "supply_status": "adequate",
    "staffed_beds": 80,
    "total_beds": 100
  }],
  "active_alerts": []
}
```

Runtime errors: `401` auth. The route persists a `ReadinessMetric` snapshot
for each active tenant facility and commits that snapshot. It does not modify
facility master data or alert state.

### `POST /api/v1/simulate`

Authentication: `X-API-Key`. Tenant scope: the requested facility must be an
active facility of the authenticated tenant.

Request (`SimulateRequest`):

```json
{
  "facility_code": "A-01",
  "baseline_demand_beds": 70,
  "demand_uplift_pct": 10,
  "absenteeism_pct": 25
}
```

`baseline_demand_beds` is required and ranges from 0 to 100000. Uplift ranges
from 0 to 500 percent; absenteeism ranges from 0 to 100 percent.

Response `200` (`SimulateResponse`):

```json
{
  "simulation_id": "simulation-uuid",
  "facility_code": "A-01",
  "baseline_staffed_beds": 80,
  "simulated_staffed_beds": 60,
  "projected_demand_beds": 77,
  "shortfall_beds": 17,
  "capacity_utilization_pct": 128.33,
  "note": "Deterministic scenario calculation, not a validated epidemiological forecast."
}
```

Runtime errors: `401` auth, `404` facility not found for the tenant, `422`
invalid request. The simulation is hypothetical and does not change live
readiness or facility state. A `Simulation` row and a `simulation.created`
audit event are committed together; both use the same simulation ID.

### `POST /api/v1/alerts/{alert_id}/review`

Authentication: `X-API-Key`. Tenant scope: the alert must belong to the
authenticated tenant. A foreign or missing alert returns the same `404` to
avoid cross-tenant existence leakage.

Request (`AlertReviewRequest`):

```json
{
  "decision": "acknowledged",
  "note": "Reviewed against synthetic source feed",
  "officer_id": "demo-officer-01"
}
```

`decision` is one of `acknowledged`, `dismissed`, or `escalated`. `note` is at
most 2000 characters; `officer_id` is required.

Response `200` (`AlertReviewResponse`):

```json
{
  "alert_id": "alert-uuid",
  "status": "acknowledged",
  "reviewed_at": "2026-10-23T10:05:00Z",
  "audit_entry_hash": "64-character-sha256-hex"
}
```

Runtime errors: `401` auth, `404` missing/foreign alert, `409` alert already
reviewed, `422` invalid request. The alert update and `alert.reviewed` audit
event are committed in one transaction.

### `GET /api/v1/audit/verify`

Authentication: `X-API-Key`. Tenant scope: verifies only the complete persisted
SHA-256 audit chain for the authenticated tenant.

Response `200` (`AuditVerifyResponse`):

```json
{
  "valid": true,
  "checked_count": 3,
  "first_invalid_event_id": null,
  "failure_reason": null
}
```

Corruption found during verification is represented by `200` with
`valid: false` and a stable reason such as `event_hash_mismatch`,
`previous_hash_mismatch`, `invalid_genesis`, or `malformed_event`. Missing or
invalid authentication returns `401`. Verification is read-only and does not
repair events.

The existing chain uses canonical JSON over tenant, actor, action, entity type,
entity ID, payload, and previous hash; UTF-8 SHA-256; and a null genesis
previous hash. No sequence column exists.

## Persistence and restart behavior

Operational signals, alerts, readiness snapshots, simulations, and audit events
are persisted in the configured SQLAlchemy database. The in-memory Merkle
module (`app/merkle.py`) is not registered in `app/models.py`, has no database
table, startup reload, or API endpoint, and therefore does **not** survive an
application restart. The demo relies on `/api/v1/audit/verify` for durable
audit-chain verification. Durable Merkle checkpoints are explicitly out of
scope for this contract freeze.

## Route-to-screen mapping

| Future screen/component | Existing endpoint(s) | Available live data | Backend gap |
|---|---|---|---|
| Service status | `GET /healthz` | Health status and demo mode | No authenticated readiness of dependencies. |
| Facility readiness dashboard | `GET /api/v1/overview` | Four 4S scores, overall score, supply buffer/status, active alerts | No historical trend endpoint; overview writes snapshots as a side effect. |
| Signal import | `POST /api/v1/ingest` | Accepted/rejected counts, row reasons, alert count | No asynchronous job/progress endpoint. |
| Alert queue/review | `GET /api/v1/overview`, `POST /api/v1/alerts/{alert_id}/review` | Open alert evidence text, status transition, audit hash | No dedicated alert list/history endpoint. |
| What-if panel | `POST /api/v1/simulate` | Deterministic capacity result and persisted ID | No simulation history/list endpoint. |
| Audit administration | `GET /api/v1/audit/verify` | Chain validity and first failure metadata | No durable Merkle checkpoint or inclusion-proof API. |

No frontend source was created or modified in this phase.
