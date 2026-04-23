# Autonomous Load Governor (ALG)

ALG is a Python-first closed-loop performance testing system. It runs a FastAPI
system under test, drives load with Locust, adapts users in real time, detects
stability and breakpoint behavior, and uses an OpenAI-compatible LLM to explain
each interval and generate batched markdown + HTML reports on a timed cadence.

The local workflow is intentionally Docker-free: setup installs Python
dependencies into `.venv`, then the controller runs the Locust load driver
inside the Python process.

## What It Demonstrates

- Closed-loop load control instead of fixed-load testing.
- Live adjustment of virtual users based on latency, errors, CPU, and RPS.
- Stability-window detection and breakpoint classification.
- LLM-directed scaling decisions every interval with periodic LLM summary reports.
- HTML report viewer exposed by the FastAPI app.
- A FastAPI test service with `GET`, `POST`, `PUT`, and `DELETE` endpoints.

## Architecture

```text
Locust load driver
        -> FastAPI system under test
        -> Controller collects live stats
        -> LLM decides user scaling each interval
        -> Decision engine records run state and summaries
        -> LLM summarizes batched intervals into timed reports
```

Runtime metrics come from:

- Locust: p95 latency, error rate, RPS.
- FastAPI `/runtime`: system CPU, process CPU, memory, uptime.

## Project Layout

```text
app/                  FastAPI test service
controller/           adaptive controller and decision engine
llm/                  OpenAI-compatible LLM client
load/                 Locust user behavior
scripts/              Windows setup and run scripts
reports/              generated reports, ignored by git
alg.settings.json     committed runtime/controller tuning
```

## Security

Secrets belong in local `.env`, which is ignored by git. Runtime tuning belongs
in committed `alg.settings.json`.

Do not put API keys in commands, source files, screenshots, shell history, or
README examples. Rotate the key if it is ever exposed.

Required LLM values:

```env
ALG_LLM_API_KEY=your_key_here
ALG_LLM_BASE_URL=https://api.openai.com/v1
ALG_LLM_MODEL=your_chat_model_here
```

The controller has no non-LLM fallback. If the key or model is missing, startup
fails. If the LLM API rate-limits the run, the controller retries and then exits
cleanly rather than inventing explanations.

## Setup

From the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-local.ps1
```

This creates `.venv` and installs dependencies from `app/requirements.txt`.

Create a local `.env` for secrets only:

```powershell
notepad .env
```

Add at minimum:

```env
ALG_LLM_API_KEY=your_key_here
ALG_LLM_BASE_URL=https://api.openai.com/v1
ALG_LLM_MODEL=gpt-4.1-mini
```

Then edit `alg.settings.json` for runtime behavior, for example:

```json
{
  "ALG_INITIAL_USERS": 10,
  "ALG_STEP_USERS": 10,
  "ALG_INTERVAL_SECONDS": 60,
  "ALG_MAX_INTERVALS": 5,
  "ALG_REPORT_EVERY_SECONDS": 60,
  "ALG_LLM_MAX_RETRIES": 3,
  "ALG_LLM_RETRY_SECONDS": 20
}
```

## Run

Start the full local stack:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

The script opens two windows:

- `ALG FastAPI`: starts the test service on `http://127.0.0.1:8000`
- `ALG Controller`: starts the adaptive controller and Locust load driver

Close those windows to stop the run.

## Verify

Open the FastAPI docs:

```text
http://127.0.0.1:8000/docs
```

Useful endpoints:

- `GET /health`
- `GET /runtime`
- `GET /work?work_ms=20&fail_pct=0`
- `GET /items/{item_id}`
- `POST /items`
- `PUT /items/{item_id}`
- `DELETE /items/{item_id}`

Example `POST` or `PUT` body:

```json
{
  "name": "demo-widget",
  "description": "Synthetic item used for load testing.",
  "price": 25.0
}
```

In the controller window, expect lines like:

```text
[1/5] users=10 p95=120.0ms errors=0.000% system_cpu=35.0% app_cpu=18.0% rps=18.4 action=hold->10 bottleneck=none
```

Open the HTML report viewer:

```text
http://127.0.0.1:8000/reports
```

If a report already exists, `/reports` redirects to the newest HTML report:

```text
http://127.0.0.1:8000/reports/latest
```

The controller updates `reports/latest.html` every interval with a live HTML
snapshot, so the report page can be refreshed or polled while the run is active.

The controller collects metrics every interval and now asks the LLM to choose
the next scaling action every interval. The separate summary report cadence
still controls when the full markdown/HTML performance report is generated.

By default, `ALG_LATENCY_THRESHOLD_MS=2000`, which means a run is considered
healthy up to a 2 second p95 latency threshold unless you override it in `.env`.

## Analysis Output

During a run, ALG writes batched markdown and HTML reports under:

```text
reports/
```

The FastAPI app also serves them at:

```text
/reports
/reports/latest
/reports/files/{filename}
```

Each live HTML snapshot and periodic report summarizes:

- current system CPU
- current app process CPU

- max stable users
- detected breakpoint, if any
- bottleneck classification
- supporting metrics
- suggested fixes

`reports/latest.html` is updated every interval for live viewing and is
overwritten by the newest periodic LLM-backed report when a report window
completes, so there is always a stable link for the newest user-friendly page.

`reports/` is ignored because generated LLM output may contain run details.

## Decision Logic

The controller evaluates each interval:

```text
controller collects metrics
-> LLM receives latest metrics, recent history, thresholds, and user bounds
-> LLM returns JSON with:
   - action
   - target_users
   - reason
   - bottleneck
   - breakpoint_detected
-> controller clamps target_users to configured min/max bounds
```

Bottleneck classes:

- `CPU saturation`
- `error saturation`
- `latency collapse`
- `none`

## Configuration

Edit `.env` for provider settings:

```env
ALG_TARGET_URL=http://127.0.0.1:8000
ALG_LLM_API_KEY=your_key_here
ALG_LLM_BASE_URL=https://api.openai.com/v1
ALG_LLM_MODEL=gpt-4.1-mini
```

Edit `alg.settings.json` for controller behavior:

```json
{
  "ALG_LLM_MAX_RETRIES": 3,
  "ALG_LLM_RETRY_SECONDS": 20,
  "ALG_INITIAL_USERS": 10,
  "ALG_MIN_USERS": 1,
  "ALG_MAX_USERS": 1000,
  "ALG_STEP_USERS": 10,
  "ALG_SPAWN_RATE": 10,
  "ALG_INTERVAL_SECONDS": 60,
  "ALG_MAX_INTERVALS": 5,
  "ALG_REPORT_EVERY_SECONDS": 60,
  "ALG_LATENCY_THRESHOLD_MS": 2000,
  "ALG_ERROR_RATE_THRESHOLD": 0.02,
  "ALG_CPU_THRESHOLD_PERCENT": 80,
  "ALG_STABLE_INTERVALS": 2,
  "ALG_KNEE_LATENCY_MULTIPLIER": 2.5
}
```

Workload tuning still lives in `.env` if you want to override the FastAPI test
traffic behavior:

```env
WORK_MS=20
FAIL_PCT=0
SLEEP_SECONDS=1
```

Increase `WORK_MS` to make FastAPI more CPU-bound. Increase `FAIL_PCT` to
simulate error saturation.

## Troubleshooting

PowerShell profile errors:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

LLM `429 Too Many Requests`:

- ALG now waits at least 120 seconds before retrying a `429`
- reduce `ALG_MAX_INTERVALS`
- increase `ALG_INTERVAL_SECONDS`
- use a lighter model such as `gpt-4.1-mini`
- check API billing/quota/model access

Port already in use:

- close old `ALG FastAPI` windows
- or run with another port:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run-local.ps1 -AppPort 8010
```

No report generated:

- check whether the controller stopped due to an LLM error
- confirm `.env` has `ALG_LLM_API_KEY` and `ALG_LLM_MODEL`
- wait until `ALG_REPORT_EVERY_SECONDS` has elapsed
- open `http://127.0.0.1:8000/reports` to view the latest HTML output

## Manual Run

Setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app\requirements.txt
notepad .env
```

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
$env:ALG_TARGET_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe controller\main.py
```
