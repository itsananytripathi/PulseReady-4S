# H6–H8 Backend Hardening Report

## Scope

Added isolated FastAPI/SQLAlchemy integration coverage for synthetic CSV and JSON ingestion, row validation, freshness, finite non-negative values, facility and tenant boundaries, deterministic simulation edge cases, alert review, and audit linkage. The only application change is finite numeric validation via `math.isfinite`; no new product feature or API route was added.

## Test coverage

- `tests/test_api_hardening.py`: 15 new test cases, including parametrized edge cases.
- Existing `tests/test_analytics.py`: 3 test cases.
- The fixture uses a per-test temporary SQLite database and two synthetic tenants. It never opens `pulseready.db`.

Run from this directory:

```bash
pytest -q
```

## Verification evidence

Static editor diagnostics reported no errors for the changed application and test files.

The test suite and clean startup could not be executed in this environment:

1. The repository virtualenv's Python link points to missing `/opt/homebrew/Caskroom/miniforge/base/bin/python`; invoking its pytest launcher failed with `Operation not permitted`.
2. `/usr/bin/python3 -m pytest -q` and `/usr/bin/python3 -m py_compile app/*.py tests/*.py` failed because the system Python invokes macOS `xcode-select`, while command-line developer tools are unavailable.
3. The shared Swagger page was checked at `http://127.0.0.1:8000/healthz`; the request returned `ERR_CONNECTION_REFUSED`, so a clean application startup was not demonstrated.

Accordingly, no test is reported as passing. No failure count from pytest is available because pytest did not start.

## Audit verification and limitations

The tests verify actor, entity type/id, decision in the canonical payload, timestamp presence, SHA-256 entry hashes, and previous-hash linkage. The implementation remains application-level and tamper-evident, not inherently immutable. A privileged database administrator can alter rows. Concurrent writers can also race while selecting the chain head; production use requires database serialization/constraints and external checkpoints or WORM storage plus an independent verifier.

## Remaining risks, highest first

1. The application has no database-level RLS or equivalent defense if a query omits a tenant predicate; production deployment should add PostgreSQL RLS and scoped DB roles.
2. Audit ordering is not serialized for concurrent writers and has no external anchoring or verification job.
3. Demo API-key authentication lacks production key management, rotation, rate limiting, TLS enforcement, and user/role authorization.
4. `create_all()` is suitable for the demo only; controlled migrations are required before deployment.
5. Analytics and simulation are transparent prototype heuristics, not clinically validated forecasts or decisions.
