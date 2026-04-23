from __future__ import annotations

import math
import random
import time
from typing import Callable

import psutil
from fastapi import FastAPI, HTTPException, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
CPU_PERCENT = Gauge("alg_app_cpu_percent", "Application container CPU percent.")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            path = request.url.path
            elapsed = time.perf_counter() - start
            REQUEST_COUNT.labels(request.method, path, status).inc()
            REQUEST_LATENCY.labels(request.method, path, status).observe(elapsed)


app = FastAPI(title="ALG Test Service")
app.add_middleware(MetricsMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/work")
def work(
    work_ms: int = Query(default=20, ge=0, le=5000),
    fail_pct: float = Query(default=0.0, ge=0.0, le=100.0),
) -> dict[str, float | int | str]:
    deadline = time.perf_counter() + (work_ms / 1000)
    value = 0.0

    while time.perf_counter() < deadline:
        value += math.sqrt((int(value) % 1000) + 1)

    if fail_pct > 0 and random.random() < (fail_pct / 100):
        raise HTTPException(status_code=500, detail="Synthetic failure")

    return {
        "status": "ok",
        "work_ms": work_ms,
        "result": round(value, 3),
    }


@app.get("/metrics")
def metrics() -> Response:
    CPU_PERCENT.set(psutil.cpu_percent(interval=None))
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
