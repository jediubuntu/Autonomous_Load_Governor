# Autonomous Load Governor (ALG)

ALG is a closed-loop performance testing demo. It drives k6 load, reads live
Prometheus metrics, adjusts virtual users, detects system limits, and uses an
OpenAI-compatible LLM to explain decisions and produce the final report.

## Security

Secrets belong in `.env`, which is ignored by git. Commit `.env.example`, not
`.env`.

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

## Local endpoints

- FastAPI app: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- k6 API: `http://localhost:6565`

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
