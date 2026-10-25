# PulseReady 4S frontend

This Vite/React/TypeScript dashboard is a separate frontend for the existing
FastAPI backend. It uses only the frozen routes documented in
`../pulseready_backend/docs/API_CONTRACTS.md`; production UI code never uses
fake operational data.

## Prerequisites

- Node.js 20+ and npm 10+.
- The backend running at `http://127.0.0.1:8000`.
- A local synthetic demo API key configured by the backend.

## Install and configure

```bash
npm install
cp .env.example .env.local
# Set VITE_API_KEY to the disposable local synthetic demo key.
```

`VITE_*` values are embedded in the browser bundle and are public. Use only a
minimally privileged synthetic demo key. Never put a production credential or
patient data in `.env` or source control. The frontend does not persist keys in
local storage and never logs them.

## Development, tests, and build

```bash
npm run dev
npm test
npm run typecheck
npm run build
```

The development server normally runs on `http://localhost:5173`. The backend
allows the two explicit local origins `http://localhost:5173` and
`http://127.0.0.1:5173` through `CORS_ORIGINS`. Production or shared origins
must be explicitly approved and configured; wildcard origins are not allowed.

## Troubleshooting

- “API key is not configured”: set `VITE_API_KEY` in `.env.local` and restart Vite.
- “Backend is unreachable”: start FastAPI and verify `GET /healthz`; use the
  configured `VITE_API_BASE_URL` if it is not `http://127.0.0.1:8000`.
- Validation or authorization errors are shown from safe status-aware UI
  messages. Non-idempotent uploads, reviews, and simulations are not silently
  retried; if a response is lost, verify state through the read endpoints.

All fixtures in frontend tests are synthetic contract-shaped responses. They
prove UI behavior only, not live backend integration.
