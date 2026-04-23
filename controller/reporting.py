from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from controller.decision_engine import Decision, EngineSummary, MetricsSnapshot


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_text_report(report_dir: Path, report: str, timestamp: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"alg_report_{timestamp}.md"
    path.write_text(report, encoding="utf-8")
    return path


def write_html_report(
    report_dir: Path,
    *,
    report: str,
    history: list[MetricsSnapshot],
    decisions: list[Decision],
    summary: EngineSummary,
    timestamp: str,
    title: str,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"alg_report_{timestamp}.html"
    html = render_html_report(
        report=report,
        history=history,
        decisions=decisions,
        summary=summary,
        title=title,
    )
    path.write_text(html, encoding="utf-8")
    (report_dir / "latest.html").write_text(html, encoding="utf-8")
    return path


def render_html_report(
    *,
    report: str,
    history: list[MetricsSnapshot],
    decisions: list[Decision],
    summary: EngineSummary,
    title: str,
) -> str:
    latest = history[-1] if history else None
    latest_decision = decisions[-1] if decisions else None
    rows = "\n".join(
        render_row(index, snapshot, decisions[index] if index < len(decisions) else None)
        for index, snapshot in enumerate(history)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #dde3ee;
      --accent: #2563eb;
      --good: #047857;
      --warn: #b45309;
      --bad: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.5;
    }}
    header {{
      background: #101827;
      color: #fff;
      padding: 28px 32px;
    }}
    header p {{ color: #cbd5e1; margin: 6px 0 0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ margin: 0; }}
    h2 {{ font-size: 18px; margin-bottom: 14px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }}
    .card, .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .card {{ padding: 18px; }}
    .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .value {{ font-size: 26px; font-weight: 700; margin-top: 6px; }}
    .section {{ padding: 20px; margin-top: 20px; overflow: hidden; }}
    .report {{
      white-space: pre-wrap;
      font-family: Segoe UI, Arial, sans-serif;
      color: #243047;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .pill {{ display: inline-block; padding: 3px 8px; border-radius: 999px; background: #eff6ff; color: var(--accent); font-weight: 600; }}
    .bad {{ color: var(--bad); }}
    .good {{ color: var(--good); }}
    .warn {{ color: var(--warn); }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      main {{ padding: 18px; }}
    }}
    @media (max-width: 560px) {{
      .grid {{ grid-template-columns: 1fr; }}
      table {{ font-size: 12px; }}
      th, td {{ padding: 8px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p>Generated {escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))}</p>
  </header>
  <main>
    <section class="grid">
      {metric_card("Current Users", latest.users if latest else 0)}
      {metric_card("P95 Latency", f"{latest.latency_p95_ms:.1f} ms" if latest else "0 ms")}
      {metric_card("Error Rate", f"{latest.error_rate:.3%}" if latest else "0.000%")}
      {metric_card("Current RPS", f"{latest.rps:.1f}" if latest else "0.0")}
      {metric_card("Max Stable", summary.max_stable_users)}
      {metric_card("Breakpoint", summary.breakpoint_users or "not detected")}
      {metric_card("Bottleneck", summary.bottleneck)}
      {metric_card("Last Action", latest_decision.action if latest_decision else "none")}
    </section>
    <section class="section">
      <h2>LLM Analysis</h2>
      <div class="report">{escape(report)}</div>
    </section>
    <section class="section">
      <h2>Interval Metrics</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Users</th>
            <th>P95</th>
            <th>Errors</th>
            <th>CPU</th>
            <th>RPS</th>
            <th>Action</th>
            <th>Bottleneck</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def metric_card(label: str, value: object) -> str:
    return f"""<article class="card">
        <div class="label">{escape(label)}</div>
        <div class="value">{escape(str(value))}</div>
      </article>"""


def render_row(index: int, snapshot: MetricsSnapshot, decision: Decision | None) -> str:
    action = decision.action if decision else "none"
    bottleneck = decision.bottleneck if decision else "none"
    action_class = "good" if action == "increase" else "bad" if action == "decrease" else "warn"
    return f"""<tr>
            <td>{index + 1}</td>
            <td>{snapshot.users}</td>
            <td>{snapshot.latency_p95_ms:.1f} ms</td>
            <td>{snapshot.error_rate:.3%}</td>
            <td>{snapshot.cpu_percent:.1f}%</td>
            <td>{snapshot.rps:.1f}</td>
            <td><span class="pill {action_class}">{escape(action)}</span></td>
            <td>{escape(bottleneck)}</td>
          </tr>"""


def decisions_as_dicts(decisions: list[Decision]) -> list[dict]:
    return [asdict(decision) for decision in decisions]
