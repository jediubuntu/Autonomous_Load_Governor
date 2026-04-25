from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import json

from controller.decision_engine import Decision, EngineSummary, MetricsSnapshot

APP_DIR = Path(__file__).resolve().parents[1] / "app"
TEMPLATE_DIR = APP_DIR / "templates"


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

    template = (TEMPLATE_DIR / "report.html").read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": escape(title),
        "{{GENERATED_AT}}": escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")),
        "{{INTERVAL_COUNT}}": str(len(history)),
        "{{LATEST_ACTION}}": escape(latest_decision.action if latest_decision else "none"),
        "{{METRIC_CARDS}}": render_metric_cards(latest, summary, latest_decision),
        "{{REPORT_HTML}}": report_html,
        "{{TIMELINE_HTML}}": render_timeline(history, decisions),
        "{{ROWS_HTML}}": rows,
        "{{CHART_DATA_JSON}}": escape(json.dumps(chart_data)),
    }

    html = template
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


def render_metric_cards(
    latest: MetricsSnapshot | None,
    summary: EngineSummary,
    latest_decision: Decision | None,
) -> str:
    return "\n".join(
        [
            metric_card("Current Users", latest.users if latest else 0, "Active load level"),
            metric_card("P95 Latency", f"{latest.latency_p95_ms:.1f} ms" if latest else "0 ms", "Tail latency now"),
            metric_card("Error Rate", f"{latest.error_rate:.3%}" if latest else "0.000%", "Observed failures"),
            metric_card("Current RPS", f"{latest.rps:.1f}" if latest else "0.0", "Throughput"),
            metric_card("System CPU", f"{latest.system_cpu_percent:.1f}%" if latest else "0.0%", "Whole laptop / machine"),
            metric_card("App Process CPU", f"{latest.process_cpu_percent:.1f}%" if latest else "0.0%", "FastAPI process only"),
            metric_card("Max Stable", summary.max_stable_users, "Best stable user count"),
            metric_card("Breakpoint", summary.breakpoint_users or "not detected", "First unstable user count"),
            metric_card("Bottleneck", summary.bottleneck, "Current classification"),
            metric_card("Last Action", latest_decision.action if latest_decision else "none", "Most recent controller choice"),
        ]
    )


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
