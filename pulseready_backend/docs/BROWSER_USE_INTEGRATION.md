# Browser Use Cloud V4 integration

PulseReady 4S contains an optional server-side adapter at
`app/integrations/browser_use_adapter.py` for Browser Use Cloud V4 hosted
agent runs. It is disabled unless `browser_use` is listed in
`ENABLED_INTEGRATIONS` and `BROWSER_USE_API_KEY` is configured on the backend
server. The key is never returned to clients or written to logs.

The adapter calls the official V4 SDK surface:

```python
from app.integrations.browser_use_adapter import run_hosted_task

result = await run_hosted_task(task="Return the title of example.com.")
```

It omits model and model-parameter arguments so the V4 service default is
selected, enforces a hard maximum cost of USD 1.00 per run, waits for a
terminal status, requires a successful result with output, and closes the SDK
client when supported. It does not retry an ambiguous create request. An
abandoned remote run must be explicitly cancelled with `cancel_run` when the
SDK exposes cancellation.

The current repository environment does not contain the SDK package. Install
the declared backend dependencies before enabling the integration:

```bash
cd pulseready_backend
./.venv/bin/python -m pip install -r requirements.txt
```

No live task was submitted during tests, so no Browser Use credits were spent.
The adapter tests use synthetic mocked SDK clients only. A real API key and
explicit approval are required before any live run is attempted.
