from __future__ import annotations

import math
import random
import threading
import time
from pathlib import Path

import psutil
from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field


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
START_TIME = time.time()


app = FastAPI(title="ALG Test Service")
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runtime")
def runtime() -> dict[str, float | int]:
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "process_cpu_percent": psutil.Process().cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "uptime_seconds": round(time.time() - START_TIME, 3),
    }


@app.get("/reports", response_class=HTMLResponse)
def latest_report() -> Response:
    latest = REPORT_DIR / "latest.html"
    if not latest.exists():
        html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ALG Reports</title>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; margin: 40px; color: #172033; }
    .box { max-width: 760px; border: 1px solid #dde3ee; border-radius: 8px; padding: 24px; }
    h1 { margin-top: 0; }
    code { background: #f2f4f7; padding: 2px 5px; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="box">
    <h1>No ALG report yet</h1>
    <p>The controller writes reports after the configured report interval.</p>
    <p>Default: <code>ALG_REPORT_EVERY_SECONDS=60</code></p>
  </div>
</body>
</html>"""
        return HTMLResponse(html)
    return FileResponse(latest, media_type="text/html")


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
