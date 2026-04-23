# Autonomous Load Governor (ALG)

ALG is a closed-loop performance testing demo. It drives k6 load, reads live
Prometheus metrics, adjusts virtual users, detects system limits, and uses an
OpenAI-compatible LLM to explain decisions and produce the final report.

## Security

Secrets belong in `.env`, which is ignored by git. Commit `.env.example`, not
`.env`.

Do not put API keys in commands, source files, screenshots, shell history, or
README examples. Rotate the key if it is ever exposed.

Required LLM values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill these values:

```env
ALG_LLM_API_KEY=your_key_here
ALG_LLM_BASE_URL=https://api.openai.com/v1
ALG_LLM_MODEL=your_chat_model_here
```

The controller has no non-LLM fallback. If the key or model is missing, startup
fails.

Generated reports are written under `reports/`, which is ignored because LLM
outputs can contain operational details from the run.

## Run with Docker

Start the app, Prometheus, and k6:

```powershell
docker compose --profile load up --build app prometheus k6
```

In another terminal, run the controller locally:

```powershell
python controller/main.py
```

Or run the controller in Docker after `.env` is populated:

```powershell
docker compose --profile load --profile controller up --build
```

## Run without Docker

Use this path when Docker Desktop is unavailable or restricted.

Required local tools:

- Python 3.11+
- k6 for Windows
- Prometheus for Windows

Prepare Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r app\requirements.txt
```

Create your local secret file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in `ALG_LLM_API_KEY` and `ALG_LLM_MODEL`.

Terminal 1: start FastAPI:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2: start Prometheus:

```powershell
prometheus.exe --config.file=metrics\prometheus.local.yml --storage.tsdb.path=prometheus-data
```

Terminal 3: start k6 with the control API enabled:

```powershell
$env:TARGET_URL = "http://127.0.0.1:8000"
$env:INITIAL_VUS = "50"
$env:MAX_VUS = "1000"
k6 run --address 127.0.0.1:6565 load\script.js
```

Terminal 4: start the controller:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PROMETHEUS_URL = "http://127.0.0.1:9090"
$env:K6_API_URL = "http://127.0.0.1:6565"
python controller\main.py
```

For Command Prompt instead of PowerShell, set variables like this:

```cmd
set TARGET_URL=http://127.0.0.1:8000
set INITIAL_VUS=50
set MAX_VUS=1000
```

## Local endpoints

- FastAPI app: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- k6 API: `http://localhost:6565`

Demo API:

- `GET /items/{item_id}`
- `POST /items`
- `PUT /items/{item_id}`
- `DELETE /items/{item_id}`

Example payload for `POST` and `PUT`:

```json
{
  "name": "demo-widget",
  "description": "Synthetic item used for load testing.",
  "price": 25.0
}
```

## How the loop works

1. k6 runs an `externally-controlled` scenario.
2. The controller queries Prometheus for p95 latency, error rate, CPU, and RPS.
3. The decision engine increases load after stable windows.
4. The decision engine backs off on CPU saturation, error saturation, or latency collapse.
5. Every decision is explained by the configured LLM.
6. A final markdown report is written under `reports/`.

## Useful knobs

Edit `.env`:

```env
ALG_INITIAL_USERS=50
ALG_MAX_USERS=1000
ALG_STEP_USERS=50
ALG_INTERVAL_SECONDS=30
ALG_LATENCY_THRESHOLD_MS=500
ALG_ERROR_RATE_THRESHOLD=0.02
ALG_CPU_THRESHOLD_PERCENT=80
ALG_STABLE_INTERVALS=2
```

k6 workload controls:

```env
WORK_MS=20
FAIL_PCT=0
SLEEP_SECONDS=1
```

Increase `WORK_MS` to make the FastAPI service more CPU-bound. Increase
`FAIL_PCT` to simulate error saturation.
