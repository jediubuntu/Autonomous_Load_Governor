# Autonomous Load Governor (ALG)

ALG is a Python-first closed-loop performance testing system. It runs a FastAPI
system under test, drives load with Locust, adapts users in real time, detects
stability and breakpoint behavior, and uses an OpenAI-compatible LLM to explain
each decision and generate a final report.

The local workflow is intentionally Docker-free: setup installs Python
dependencies into `.venv`, then the controller runs the Locust load driver
inside the Python process.

## What It Demonstrates

- Closed-loop load control instead of fixed-load testing.
- Live adjustment of virtual users based on latency, errors, CPU, and RPS.
- Stability-window detection and breakpoint classification.
- LLM-generated explanations and final performance summary.
- A FastAPI test service with `GET`, `POST`, `PUT`, and `DELETE` endpoints.

## Architecture

```text
Locust load driver
        -> FastAPI system under test
        -> Controller collects live stats
        -> Decision engine adjusts users
        -> LLM explains decisions and report
```

Runtime metrics come from:

- Locust: p95 latency, error rate, RPS.
- FastAPI `/runtime`: CPU, process CPU, memory, uptime.

## Project Layout

```text
app/                  FastAPI test service
controller/           adaptive controller and decision engine
llm/                  OpenAI-compatible LLM client
load/                 Locust user behavior
scripts/              Windows setup and run scripts
reports/              generated reports, ignored by git
.env.example          safe config template
```

## Security

Secrets belong in `.env`, which is ignored by git. Commit `.env.example`, not
`.env`.

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

From `D:\Personal\Projects\ALG`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-local.ps1
```

This creates `.venv`, installs dependencies from `app/requirements.txt`, and
creates `.env` from `.env.example` if `.env` does not already exist.

Edit `.env`:

```powershell
notepad .env
```

At minimum, fill:

```env
ALG_LLM_API_KEY=your_key_here
ALG_LLM_MODEL=gpt-4.1-mini
```

For a safer low-cost demo, these settings are reasonable:

```env
ALG_LLM_MODEL=gpt-4.1-mini
ALG_LLM_MAX_RETRIES=3
ALG_LLM_RETRY_SECONDS=20
ALG_INITIAL_USERS=10
ALG_STEP_USERS=10
ALG_INTERVAL_SECONDS=60
ALG_MAX_INTERVALS=5
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
[1/5] users=10 p95=120.0ms errors=0.000% cpu=35.0% rps=18.4 action=hold->10 bottleneck=none
```

The LLM explanation prints below each decision after the API responds.

## Analysis Output

At the end of a successful run, ALG writes a markdown report under:

```text
reports/
```

The report summarizes:

- max stable users
- detected breakpoint, if any
- bottleneck classification
- supporting metrics
- suggested fixes

`reports/` is ignored because generated LLM output may contain run details.

## Decision Logic

The controller evaluates each interval:

```text
if error_rate > threshold:
    decrease users
elif latency > threshold and cpu > threshold:
    decrease users
elif latency jumps versus recent stable baseline:
    decrease users
elif stable for N intervals:
    increase users
else:
    hold users
```

Bottleneck classes:

- `CPU saturation`
- `error saturation`
- `latency collapse`
- `none`

## Configuration

Edit `.env`:

```env
ALG_TARGET_URL=http://127.0.0.1:8000
ALG_LLM_API_KEY=your_key_here
ALG_LLM_BASE_URL=https://api.openai.com/v1
ALG_LLM_MODEL=gpt-4.1-mini
ALG_LLM_MAX_RETRIES=3
ALG_LLM_RETRY_SECONDS=20
ALG_INITIAL_USERS=10
ALG_MIN_USERS=1
ALG_MAX_USERS=1000
ALG_STEP_USERS=10
ALG_SPAWN_RATE=10
ALG_INTERVAL_SECONDS=60
ALG_MAX_INTERVALS=5
ALG_LATENCY_THRESHOLD_MS=500
ALG_ERROR_RATE_THRESHOLD=0.02
ALG_CPU_THRESHOLD_PERCENT=80
ALG_STABLE_INTERVALS=2
ALG_KNEE_LATENCY_MULTIPLIER=2.5
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

## Manual Run

Setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r app\requirements.txt
Copy-Item .env.example .env
notepad .env
```

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
$env:ALG_TARGET_URL = "http://127.0.0.1:8000"
python controller\main.py
```
