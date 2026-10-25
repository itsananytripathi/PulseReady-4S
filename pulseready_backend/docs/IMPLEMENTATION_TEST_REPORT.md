# Implementation test report

## Phase 2 verification

The Phase 2 baseline was run before Phase 2 edits:

- `./.venv/bin/python -m pytest -q` — 62 passed, 0 failed, 0 skipped, 0 errors, exit 0.

No Phase 2 source changes were required for durable Merkle storage. Inspection
confirmed that checkpoints are in-memory dataclasses only and are not loaded by
application startup. The contract freeze documents this as an explicit demo
limitation; the existing persisted `/api/v1/audit/verify` chain remains the
durable audit verification mechanism.

## Commands

- `./.venv/bin/python -m pytest -q` — prior implementation baseline: 45 passed, 0 failed, 0 skipped, 0 errors, exit 0.
- `./.venv/bin/python -m pytest --collect-only -q` — final collection: 62 tests collected, exit 0.
- `./.venv/bin/python -m pytest -q` — final regression: 62 passed, 0 failed, 0 skipped, 0 errors, exit 0.
- `./.venv/bin/python - <<'PY' ...` — runtime route/OpenAPI inventory; exit 0.

Python: 3.14.8. The existing suite emitted three deprecation warnings from
FastAPI/Starlette lifecycle and TestClient compatibility; no warning was
promoted to an error.

## Added coverage

`tests/test_simulation.py` covers deterministic repeatability, input changes,
zero capacity, validation, serialization, and concurrent isolation.
`tests/test_fhir_mappings.py` covers versioned Observation and minimal Patient
mapping, absent/null/unsupported input, and mapping-name allowlisting.
`tests/test_merkle.py` covers empty/single/odd trees, inclusion proofs, and
fail-closed tampering cases. Existing API hardening, smoke, audit, fixture,
security, and focused FHIR tests remain unchanged.

## Security and limitations

Tests continue to cover missing/invalid keys, tenant scope, upload limits,
malformed values, simulation validation, audit read-only behavior, and safe
isolated seeding. No external adapter exists, so no live-network failure path
was introduced. The local FHIR checker and mapping interpreter are focused
synthetic checks, not full R4/profile/terminology conformance. Merkle support is
not persisted and does not provide independent anchoring or administrator-proof
immutability. Human review of deployment secrets, migrations, licenses, and
production authorization remains required.
