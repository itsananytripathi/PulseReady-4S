# Frontend API mapping

The frontend lives in `frontend/` and uses a centralized typed client in
`frontend/src/lib/api/`. There are no additional application endpoints.

| Screen | Endpoint | Fields used | Actions and error states |
|---|---|---|---|
| Operations overview | `GET /api/v1/overview` | `generated_at`, `readiness[]` four scores, supply buffer/status, beds, `active_alerts[]` | Loading, empty facility/alert states, retryable backend error. |
| Alerts & evidence | `GET /api/v1/overview`; `POST /api/v1/alerts/{alert_id}/review` | Alert ID, facility code, severity, status, title, explanation, created timestamp; review response status/hash | Requires officer ID; disables duplicate submission; invalidates overview only after success; shows safe `401/404/409/422` errors. |
| What-if simulation | `POST /api/v1/simulate` | Exact request constraints and all `SimulateResponse` fields | Client validates documented ranges; pending/error states; results labeled hypothetical. No client-side calculation. |
| Signal ingestion | `POST /api/v1/ingest` | File contract; accepted/rejected counts, row reasons, alert count, note | Server-confirmed summary; row-level reasons; no success shown on failure. |
| Audit integrity | `GET /api/v1/audit/verify` | `valid`, `checked_count`, `first_invalid_event_id`, `failure_reason` | Separates request failure from completed-invalid verification; no Merkle endpoint is assumed. |
| Connection status | `GET /healthz` | `status`, `mode` | Header indicator is separate from operational freshness and tenant data. |

The backend has no dedicated alert list, simulation history, freshness detail,
or durable Merkle-checkpoint endpoint, so the UI does not invent those views or
fields. The backend allows the two explicit local development origins through
`CORS_ORIGINS`; production or shared origins require explicit configuration.
No wildcard origin or credentialed browser session is used.
