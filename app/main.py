from __future__ import annotations

import math
import random
import threading
import time
from pathlib import Path

import psutil
from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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
def reports_home() -> Response:
    reports = sorted(REPORT_DIR.glob("alg_report_*.html"), reverse=True)
    latest = REPORT_DIR / "latest.html"

    if latest.exists():
        return RedirectResponse(url="/reports/latest", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    report_items = []
    for report in reports:
        modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(report.stat().st_mtime))
        report_items.append(
            f'<li><a href="/reports/files/{report.name}">{report.name}</a><span>{modified}</span></li>'
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ALG Reports</title>
  <style>
    :root {{
      --bg: #081120;
      --panel: #101a2f;
      --panel-soft: #16223d;
      --line: #263557;
      --ink: #eef4ff;
      --muted: #9fb0d1;
      --accent: #60a5fa;
      --accent-2: #22c55e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(96, 165, 250, 0.16), transparent 32%),
        radial-gradient(circle at top right, rgba(34, 197, 94, 0.14), transparent 28%),
        var(--bg);
      min-height: 100vh;
    }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 40px 24px 60px; }}
    .hero {{
      display: grid;
      grid-template-columns: 1.3fr 0.7fr;
      gap: 20px;
      align-items: stretch;
    }}
    .panel {{
      background: rgba(16, 26, 47, 0.92);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 24px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.28);
      backdrop-filter: blur(10px);
    }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ font-size: 38px; margin-bottom: 12px; }}
    .subtitle {{ color: var(--muted); font-size: 17px; max-width: 680px; }}
    .cta {{
      display: inline-block;
      margin-top: 18px;
      padding: 12px 16px;
      border-radius: 12px;
      text-decoration: none;
      background: linear-gradient(135deg, var(--accent), #3b82f6);
      color: #fff;
      font-weight: 700;
    }}
    .stack {{ display: grid; gap: 20px; margin-top: 20px; }}
    .stat {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .tile {{
      background: var(--panel-soft);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
    }}
    .tile .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .tile .value {{ font-size: 26px; font-weight: 700; margin-top: 8px; }}
    ul {{ list-style: none; margin: 0; padding: 0; }}
    li {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 0;
      border-bottom: 1px solid var(--line);
    }}
    li:last-child {{ border-bottom: 0; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
    li span {{ color: var(--muted); white-space: nowrap; }}
    code {{
      background: rgba(255,255,255,0.08);
      border: 1px solid var(--line);
      padding: 2px 6px;
      border-radius: 6px;
    }}
    @media (max-width: 860px) {{
      .hero, .stat {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 30px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="panel">
        <p style="color:#60a5fa;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">Autonomous Load Governor</p>
        <h1>Periodic HTML performance reports</h1>
        <p class="subtitle">
          ALG collects metrics every interval, makes rule-based scaling decisions every interval,
          and calls the LLM only on the configured reporting cadence. Open the latest report
          here once the controller has written one.
        </p>
        <a class="cta" href="/reports/latest">Open latest report</a>
      </div>
      <div class="panel">
        <h2>Report cadence</h2>
        <p>Default: <code>ALG_REPORT_EVERY_SECONDS=60</code></p>
        <p>Metrics and decisions continue every controller interval. The LLM runs only when the report window elapses.</p>
      </div>
    </section>
    <section class="stack">
      <div class="stat">
        <article class="tile">
          <div class="label">Available HTML Reports</div>
          <div class="value">{len(reports)}</div>
        </article>
        <article class="tile">
          <div class="label">Report Directory</div>
          <div class="value" style="font-size:18px;">reports/</div>
        </article>
        <article class="tile">
          <div class="label">Latest Shortcut</div>
          <div class="value" style="font-size:18px;">/reports/latest</div>
        </article>
      </div>
      <div class="panel">
        <h2>Generated report files</h2>
        {"<ul>" + "".join(report_items) + "</ul>" if report_items else "<p>No report files exist yet. Start the controller and wait for the first report window to complete.</p>"}
      </div>
    </section>
  </main>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/reports/latest")
def latest_report_file() -> Response:
    latest = REPORT_DIR / "latest.html"
    if not latest.exists():
        return reports_home()
    return FileResponse(latest, media_type="text/html")


@app.get("/reports/files/{filename}")
def report_file(filename: str) -> Response:
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid report filename")

    path = REPORT_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(path, media_type="text/html")


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
