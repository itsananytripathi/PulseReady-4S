# Phase 4 integration report

## Files changed

Backend: `pulseready_backend/app/config.py`, `pulseready_backend/app/main.py`,
`pulseready_backend/.env.example`, `pulseready_backend/README.md`, and
`pulseready_backend/tests/test_cors.py`.

Frontend: `frontend/.env.example`, `frontend/.gitignore`, `frontend/README.md`,
`frontend/src/lib/api/client.ts`, and `frontend/src/vite-env.d.ts`.

No route, method, request/response schema, authentication dependency, tenant
query, or deterministic analytics code was changed.

## CORS policy

The existing FastAPI application now uses Starlette `CORSMiddleware` with:

- Allowed origins: `http://localhost:5173` and `http://127.0.0.1:5173`.
- Allowed methods: `GET`, `POST`, `OPTIONS`.
- Allowed request headers: `Content-Type`, `X-API-Key`.
- `allow_credentials=False`.
- No wildcard origins.

Malformed `CORS_ORIGINS` values, wildcard origins, paths, and empty entries are
rejected during configuration parsing. CORS does not replace API-key
authentication.

## Test results

Before the CORS change:

- `./.venv/bin/python -m pytest -q` — 62 passed, 0 failed, 0 skipped, 0
  errors, exit 0.
- Frontend: 13 tests passed; typecheck and build passed.

After the change:

- `./.venv/bin/python -m pytest -q` — 70 passed, 0 failed, 0 skipped, 0
  errors, exit 0. Three existing deprecation warnings remain.
- `npm test -- --run` — 13 passed across 6 files, exit 0.
- `npm run typecheck` — exit 0.
- `npm run lint` — exit 0; this repository's lint script is the strict
  TypeScript check.
- `npm run build` — exit 0.
- `git diff --check` — clean.

## Live HTTP rehearsal

Using an isolated temporary SQLite database and synthetic credentials only:

- Allowed preflight from `http://localhost:5173`: HTTP 200 with explicit
  origin, methods, and headers.
- Allowed preflight from `http://127.0.0.1:5173`: HTTP 200 in the focused test
  suite.
- Unapproved origin: no approving CORS origin header.
- `/healthz`: HTTP 200 without an API key.
- Protected overview without a key: HTTP 401.
- Ingestion: HTTP 200, 8 accepted rows, 1 backend-generated alert.
- Overview: HTTP 200 with one readiness record and one alert.
- Simulation: HTTP 200 with actual persisted simulation output and caveat.
- Alert review: HTTP 200 with server-confirmed acknowledgement and audit hash.
- Audit verification: HTTP 200 with `valid: true`, `checked_count: 3`.
- Invalid simulation payload: HTTP 422.

The temporary database was not the normal `pulseready.db` database.

## Browser status and limitations

The Vite dev server started successfully on `http://127.0.0.1:5173` with the
disposable synthetic key supplied only through process environment. A
browser-level check could not be completed: no browser automation surface was
available for the running Chrome instance, and the computer-use binding timed
out. Therefore browser integration is not claimed as passed. Terminal
preflight and live HTTP rehearsal passed.

`npm install` reported 11 dependency audit findings in the local environment
(8 moderate, 1 high, 2 critical); no automated audit fix was applied.

## Remaining manual checks

1. Start both services using the documented commands.
2. Open the Vite URL in a browser and confirm overview, ingestion, simulation,
   alert review, and audit screens render the live temporary/demo responses.
3. Confirm browser DevTools shows the expected `Origin` and `X-API-Key` headers
   without exposing the key in application logs.
4. Replace the local disposable key and origins with deployment-approved values
   before any non-local use.
