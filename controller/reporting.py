from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import json

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
    chart_data = [
        {
            "interval": index + 1,
            "users": snapshot.users,
            "latency": round(snapshot.latency_p95_ms, 2),
            "errors": round(snapshot.error_rate * 100, 4),
            "systemCpu": round(snapshot.system_cpu_percent, 2),
            "processCpu": round(snapshot.process_cpu_percent, 2),
            "rps": round(snapshot.rps, 2),
            "action": decisions[index].action if index < len(decisions) else "none",
            "bottleneck": decisions[index].bottleneck if index < len(decisions) else "none",
        }
        for index, snapshot in enumerate(history)
    ]
    report_html = markdown_to_html(report)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f8fc;
      --bg-soft: #eef4fb;
      --panel: rgba(255, 255, 255, 0.94);
      --panel-2: rgba(248, 251, 255, 0.98);
      --line: rgba(148, 163, 184, 0.22);
      --line-strong: rgba(148, 163, 184, 0.34);
      --ink: #102033;
      --muted: #5f7188;
      --accent: #2563eb;
      --accent-2: #0ea5e9;
      --good: #16a34a;
      --warn: #d97706;
      --bad: #dc2626;
      --violet: #7c3aed;
      --pink: #db2777;
      --shadow: 0 20px 60px rgba(15, 23, 42, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; }}
    body {{
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(37, 99, 235, 0.10), transparent 30%),
        radial-gradient(circle at top right, rgba(14, 165, 233, 0.08), transparent 24%),
        linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
      color: var(--ink);
      min-height: 100vh;
      line-height: 1.5;
    }}
    .shell {{
      max-width: 1380px;
      margin: 0 auto;
      padding: 28px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.4fr 0.8fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      backdrop-filter: blur(14px);
      box-shadow: var(--shadow);
    }}
    .hero-main {{
      padding: 26px;
      position: relative;
      overflow: hidden;
    }}
    .hero-main::after {{
      content: "";
      position: absolute;
      inset: auto -60px -80px auto;
      width: 220px;
      height: 220px;
      background: radial-gradient(circle, rgba(96, 165, 250, 0.24), transparent 65%);
      pointer-events: none;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(96, 165, 250, 0.14);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-size: 34px;
      line-height: 1.15;
    }}
    .hero-copy {{
      max-width: 760px;
      color: var(--muted);
      font-size: 16px;
      margin-bottom: 0;
    }}
    .hero-side {{
      padding: 24px;
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .meta-label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    .meta-value {{
      font-size: 18px;
      font-weight: 700;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .card {{
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      min-height: 122px;
    }}
    .card .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    .card .value {{
      margin-top: 10px;
      font-size: 28px;
      font-weight: 800;
      line-height: 1.1;
    }}
    .card .hint {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .content-grid {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .section {{
      padding: 22px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 16px;
    }}
    h2 {{
      margin: 0;
      font-size: 19px;
    }}
    .subtle {{
      color: var(--muted);
      font-size: 13px;
    }}
    .report {{
      color: #203247;
      font-size: 15px;
    }}
    .report h1, .report h2, .report h3 {{
      margin-top: 0;
      color: #102033;
    }}
    .report p, .report li {{
      color: #31465f;
    }}
    .report ul {{
      padding-left: 18px;
    }}
    .report code {{
      background: #f8fbff;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 2px 6px;
      font-family: Consolas, monospace;
    }}
    .tabs {{
      display: inline-flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .tab-btn {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
      color: var(--muted);
      padding: 9px 12px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 600;
    }}
    .tab-btn.active {{
      background: rgba(96, 165, 250, 0.14);
      color: #102033;
      border-color: rgba(96, 165, 250, 0.35);
    }}
    .chart-wrap {{
      display: grid;
      gap: 14px;
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
      overflow: visible;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      color: var(--muted);
      font-size: 13px;
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .legend i {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
    }}
    .toolbar {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 14px;
    }}
    select {{
      background: #ffffff;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 9px 12px;
    }}
    .stats-table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 16px;
    }}
    .stats-table th, .stats-table td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 14px;
    }}
    .stats-table th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
      position: sticky;
      top: 0;
      background: rgba(248, 251, 255, 0.96);
      backdrop-filter: blur(10px);
    }}
    .table-wrap {{
      max-height: 420px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.72);
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .02em;
    }}
    .pill.hold {{ background: rgba(245, 158, 11, 0.14); color: #b45309; }}
    .pill.increase {{ background: rgba(34, 197, 94, 0.14); color: #166534; }}
    .pill.decrease {{ background: rgba(239, 68, 68, 0.14); color: #991b1b; }}
    .timeline {{
      display: grid;
      gap: 12px;
    }}
    .timeline-item {{
      display: grid;
      grid-template-columns: 48px 1fr;
      gap: 14px;
      align-items: start;
    }}
    .timeline-badge {{
      width: 48px;
      height: 48px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: rgba(96, 165, 250, 0.12);
      border: 1px solid rgba(96, 165, 250, 0.26);
      color: var(--accent);
      font-weight: 800;
    }}
    .timeline-card {{
      background: rgba(255,255,255,0.78);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 16px;
    }}
    .timeline-title {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 6px;
      align-items: center;
    }}
    .timeline-copy {{
      color: var(--muted);
      font-size: 14px;
    }}
    .footer-note {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 14px;
    }}
    @media (max-width: 1180px) {{
      .hero,
      .content-grid,
      .kpi-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 900px) {{
      .hero,
      .content-grid,
      .kpi-grid {{
        grid-template-columns: 1fr;
      }}
      .shell {{
        padding: 16px;
      }}
      h1 {{
        font-size: 28px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <article class="panel hero-main">
        <span class="eyebrow">ALG interactive report</span>
        <h1>{escape(title)}</h1>
        <p class="hero-copy">
          Explore live load behavior, capacity decisions, CPU signals, and LLM-backed analysis in one report.
          This page is self-contained and refresh-safe, so it works for both live snapshots and periodic summaries.
        </p>
      </article>
      <aside class="panel hero-side">
        <div>
          <div class="meta-label">Generated</div>
          <div class="meta-value">{escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))}</div>
        </div>
        <div>
          <div class="meta-label">Intervals captured</div>
          <div class="meta-value">{len(history)}</div>
        </div>
        <div>
          <div class="meta-label">Latest action</div>
          <div class="meta-value">{escape(latest_decision.action if latest_decision else "none")}</div>
        </div>
      </aside>
    </section>

    <section class="kpi-grid">
      {metric_card("Current Users", latest.users if latest else 0, "Active load level")}
      {metric_card("P95 Latency", f"{latest.latency_p95_ms:.1f} ms" if latest else "0 ms", "Tail latency now")}
      {metric_card("Error Rate", f"{latest.error_rate:.3%}" if latest else "0.000%", "Observed failures")}
      {metric_card("Current RPS", f"{latest.rps:.1f}" if latest else "0.0", "Throughput")}
      {metric_card("System CPU", f"{latest.system_cpu_percent:.1f}%" if latest else "0.0%", "Whole laptop / machine")}
      {metric_card("App Process CPU", f"{latest.process_cpu_percent:.1f}%" if latest else "0.0%", "FastAPI process only")}
      {metric_card("Max Stable", summary.max_stable_users, "Best stable user count")}
      {metric_card("Breakpoint", summary.breakpoint_users or "not detected", "First unstable user count")}
      {metric_card("Bottleneck", summary.bottleneck, "Current classification")}
      {metric_card("Last Action", latest_decision.action if latest_decision else "none", "Most recent controller choice")}
    </section>

    <section class="content-grid">
      <article class="panel section">
        <div class="section-header">
          <div>
            <h2>Interactive charts</h2>
            <div class="subtle">Switch between performance dimensions and inspect interval trends.</div>
          </div>
          <div class="tabs" id="chartTabs">
            <button class="tab-btn active" data-series="latency">Latency</button>
            <button class="tab-btn" data-series="users">Users</button>
            <button class="tab-btn" data-series="rps">RPS</button>
            <button class="tab-btn" data-series="cpu">CPU</button>
            <button class="tab-btn" data-series="errors">Errors</button>
          </div>
        </div>
        <div class="chart-wrap">
          <svg id="trendChart" viewBox="0 0 920 360" role="img" aria-label="ALG trend chart"></svg>
          <div class="legend" id="chartLegend"></div>
          <div class="footer-note">Tip: the CPU tab overlays system CPU and app process CPU so you can separate laptop-wide load from the FastAPI service process.</div>
        </div>
      </article>

      <article class="panel section">
        <div class="section-header">
          <div>
            <h2>LLM analysis</h2>
            <div class="subtle">Rendered directly from the generated markdown.</div>
          </div>
        </div>
        <div class="report">{report_html}</div>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel section">
        <div class="section-header">
          <div>
            <h2>Decision timeline</h2>
            <div class="subtle">Every interval action with context and bottleneck classification.</div>
          </div>
        </div>
        <div class="timeline">
          {render_timeline(history, decisions)}
        </div>
      </article>

      <article class="panel section">
        <div class="section-header">
          <div>
            <h2>Metrics table</h2>
            <div class="subtle">Sortable by eye and easy to cross-check with the chart.</div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="stats-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Users</th>
                <th>P95</th>
                <th>Errors</th>
                <th>System CPU</th>
                <th>App CPU</th>
                <th>RPS</th>
                <th>Action</th>
                <th>Bottleneck</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </div>

  <script>
    const DATA = {json.dumps(chart_data)};
    const SERIES = {{
      latency: {{
        title: "P95 latency (ms)",
        lines: [{{ key: "latency", label: "P95 latency", color: "#60a5fa" }}],
      }},
      users: {{
        title: "Users",
        lines: [{{ key: "users", label: "Users", color: "#a78bfa" }}],
      }},
      rps: {{
        title: "Requests per second",
        lines: [{{ key: "rps", label: "RPS", color: "#22c55e" }}],
      }},
      cpu: {{
        title: "CPU utilization (%)",
        lines: [
          {{ key: "systemCpu", label: "System CPU", color: "#f59e0b" }},
          {{ key: "processCpu", label: "App process CPU", color: "#f472b6" }},
        ],
      }},
      errors: {{
        title: "Error rate (%)",
        lines: [{{ key: "errors", label: "Error rate", color: "#ef4444" }}],
      }},
    }};

    function formatValue(seriesKey, value) {{
      if (seriesKey === "latency") return `${{value.toFixed(1)}} ms`;
      if (seriesKey === "users") return `${{value.toFixed(0)}} users`;
      if (seriesKey === "rps") return `${{value.toFixed(1)}} rps`;
      return `${{value.toFixed(2)}}%`;
    }}

    function renderChart(seriesKey) {{
      const config = SERIES[seriesKey];
      const svg = document.getElementById("trendChart");
      const legend = document.getElementById("chartLegend");
      const width = 920;
      const height = 360;
      const pad = {{ top: 24, right: 24, bottom: 54, left: 56 }};
      const plotWidth = width - pad.left - pad.right;
      const plotHeight = height - pad.top - pad.bottom;
      const points = DATA.length ? DATA : [{{ interval: 1, latency: 0, users: 0, rps: 0, systemCpu: 0, processCpu: 0, errors: 0 }}];
      const xStep = points.length > 1 ? plotWidth / (points.length - 1) : plotWidth / 2;
      const allValues = config.lines.flatMap(line => points.map(item => Number(item[line.key] || 0)));
      const maxValue = Math.max(...allValues, 1);
      const niceMax = maxValue <= 10 ? Math.ceil(maxValue + 1) : Math.ceil(maxValue * 1.1);
      const ticks = 5;
      const y = value => pad.top + plotHeight - (value / niceMax) * plotHeight;
      const x = index => pad.left + (points.length > 1 ? index * xStep : plotWidth / 2);

      let markup = `
        <rect x="0" y="0" width="${{width}}" height="${{height}}" rx="18" fill="rgba(7,17,31,0.18)"></rect>
        <text x="${{pad.left}}" y="18" fill="#97a8c5" font-size="12" font-family="Inter, Segoe UI, Arial">${{config.title}}</text>
      `;

      for (let i = 0; i <= ticks; i++) {{
        const tickValue = (niceMax / ticks) * i;
        const yPos = y(tickValue);
        markup += `
          <line x1="${{pad.left}}" y1="${{yPos}}" x2="${{width - pad.right}}" y2="${{yPos}}" stroke="rgba(148,163,184,0.12)" stroke-width="1"></line>
          <text x="${{pad.left - 10}}" y="${{yPos + 4}}" text-anchor="end" fill="#6f86a8" font-size="11">${{tickValue.toFixed(0)}}</text>
        `;
      }}

      points.forEach((point, index) => {{
        const xPos = x(index);
        markup += `
          <line x1="${{xPos}}" y1="${{pad.top}}" x2="${{xPos}}" y2="${{height - pad.bottom}}" stroke="rgba(148,163,184,0.07)" stroke-width="1"></line>
          <text x="${{xPos}}" y="${{height - pad.bottom + 24}}" text-anchor="middle" fill="#6f86a8" font-size="11">#${{point.interval}}</text>
        `;
      }});

      config.lines.forEach(line => {{
        const polyline = points.map((point, index) => `${{x(index)}},${{y(Number(point[line.key] || 0))}}`).join(" ");
        markup += `
          <polyline fill="none" stroke="${{line.color}}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="${{polyline}}"></polyline>
        `;
        points.forEach((point, index) => {{
          const value = Number(point[line.key] || 0);
          const cx = x(index);
          const cy = y(value);
          markup += `
            <circle cx="${{cx}}" cy="${{cy}}" r="5.5" fill="${{line.color}}"></circle>
            <title>${{line.label}} · interval ${{point.interval}} · ${{formatValue(seriesKey, value)}}</title>
          `;
        }});
      }});

      svg.innerHTML = markup;
      legend.innerHTML = config.lines
        .map(line => `<span><i style="background:${{line.color}}"></i>${{line.label}}</span>`)
        .join("");
    }}

    document.querySelectorAll(".tab-btn").forEach(button => {{
      button.addEventListener("click", () => {{
        document.querySelectorAll(".tab-btn").forEach(item => item.classList.remove("active"));
        button.classList.add("active");
        renderChart(button.dataset.series);
      }});
    }});

    renderChart("latency");
  </script>
</body>
</html>
"""


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    parts: list[str] = []
    in_list = False
    in_code = False

    for raw_line in lines:
        line = raw_line.rstrip()

        if line.startswith("```"):
            if in_list:
                parts.append("</ul>")
                in_list = False
            if in_code:
                parts.append("</code></pre>")
                in_code = False
            else:
                parts.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            parts.append(escape(line) + "\n")
            continue

        if not line.strip():
            if in_list:
                parts.append("</ul>")
                in_list = False
            continue

        if line.startswith("### "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h3>{escape(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{inline_markdown(line[2:])}</li>")
        else:
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<p>{inline_markdown(line)}</p>")

    if in_list:
        parts.append("</ul>")
    if in_code:
        parts.append("</code></pre>")

    return "".join(parts)


def inline_markdown(text: str) -> str:
    escaped = escape(text)
    return escaped.replace("`", "")


def metric_card(label: str, value: object, hint: str) -> str:
    return f"""<article class="card">
        <div class="label">{escape(label)}</div>
        <div class="value">{escape(str(value))}</div>
        <div class="hint">{escape(hint)}</div>
      </article>"""


def render_row(index: int, snapshot: MetricsSnapshot, decision: Decision | None) -> str:
    action = decision.action if decision else "none"
    bottleneck = decision.bottleneck if decision else "none"
    return f"""<tr>
            <td>{index + 1}</td>
            <td>{snapshot.users}</td>
            <td>{snapshot.latency_p95_ms:.1f} ms</td>
            <td>{snapshot.error_rate:.3%}</td>
            <td>{snapshot.system_cpu_percent:.1f}%</td>
            <td>{snapshot.process_cpu_percent:.1f}%</td>
            <td>{snapshot.rps:.1f}</td>
            <td><span class="pill {escape(action)}">{escape(action)}</span></td>
            <td>{escape(bottleneck)}</td>
          </tr>"""


def render_timeline(history: list[MetricsSnapshot], decisions: list[Decision]) -> str:
    items: list[str] = []
    for index, snapshot in enumerate(history):
        decision = decisions[index] if index < len(decisions) else None
        action = decision.action if decision else "none"
        bottleneck = decision.bottleneck if decision else "none"
        reason = decision.reason if decision else "No decision recorded."
        items.append(
            f"""<article class="timeline-item">
              <div class="timeline-badge">#{index + 1}</div>
              <div class="timeline-card">
                <div class="timeline-title">
                  <strong>{escape(action.title())}</strong>
                  <span class="pill {escape(action)}">{escape(action)}</span>
                </div>
                <div class="timeline-copy">
                  users={snapshot.users}, p95={snapshot.latency_p95_ms:.1f} ms,
                  system_cpu={snapshot.system_cpu_percent:.1f}%, app_cpu={snapshot.process_cpu_percent:.1f}%,
                  rps={snapshot.rps:.1f}, bottleneck={escape(bottleneck)}.
                  {escape(reason)}
                </div>
              </div>
            </article>"""
        )
    return "".join(items) or "<p class=\"subtle\">No intervals captured yet.</p>"


def decisions_as_dicts(decisions: list[Decision]) -> list[dict]:
    return [asdict(decision) for decision in decisions]
