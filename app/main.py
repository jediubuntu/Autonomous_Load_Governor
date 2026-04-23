from __future__ import annotations

import math
import random
import threading
import time
from typing import Callable

import psutil
from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field
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


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    price: float = Field(ge=0, le=1_000_000)


class Item(ItemCreate):
    id: int


def item_payload(payload: ItemCreate) -> dict[str, str | float]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


ITEMS: dict[int, Item] = {
    1: Item(id=1, name="baseline-widget", description="Seed item for read traffic.", price=25.0)
}
NEXT_ITEM_ID = 2
ITEMS_LOCK = threading.Lock()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            elapsed = time.perf_counter() - start
            REQUEST_COUNT.labels(request.method, path, status).inc()
            REQUEST_LATENCY.labels(request.method, path, status).observe(elapsed)


app = FastAPI(title="ALG Test Service")
app.add_middleware(MetricsMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/items/{item_id}")
def get_item(item_id: int) -> Item:
    with ITEMS_LOCK:
        item = ITEMS.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return item


@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate) -> Item:
    global NEXT_ITEM_ID

    with ITEMS_LOCK:
        item = Item(id=NEXT_ITEM_ID, **item_payload(payload))
        ITEMS[item.id] = item
        NEXT_ITEM_ID += 1
        return item


@app.put("/items/{item_id}")
def update_item(item_id: int, payload: ItemCreate) -> Item:
    with ITEMS_LOCK:
        if item_id not in ITEMS:
            raise HTTPException(status_code=404, detail="Item not found")

        item = Item(id=item_id, **item_payload(payload))
        ITEMS[item_id] = item
        return item


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int) -> Response:
    with ITEMS_LOCK:
        if item_id not in ITEMS:
            raise HTTPException(status_code=404, detail="Item not found")

        del ITEMS[item_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
