from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controller.config import ConfigError, Settings
from controller.decision_engine import DecisionEngine
from controller.k6_client import K6Client
from controller.metrics_client import PrometheusMetricsClient
from llm.explainer import LLMExplainer


def build_engine(settings: Settings) -> DecisionEngine:
    return DecisionEngine(
        min_users=settings.min_users,
        max_users=settings.max_users,
        step_users=settings.step_users,
        latency_threshold_ms=settings.latency_threshold_ms,
        error_rate_threshold=settings.error_rate_threshold,
        cpu_threshold_percent=settings.cpu_threshold_percent,
        stable_intervals=settings.stable_intervals,
        knee_latency_multiplier=settings.knee_latency_multiplier,
    )


def main() -> int:
    try:
        settings = Settings.from_env(ROOT)
    except (ConfigError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    metrics = PrometheusMetricsClient(settings.prometheus_url)
    k6 = K6Client(settings.k6_api_url)
    llm = LLMExplainer(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )
    engine = build_engine(settings)

    current_users = settings.initial_users
    print("Starting ALG controller")
    print(f"Prometheus: {settings.prometheus_url}")
    print(f"k6 API: {settings.k6_api_url}")
    print(f"LLM model: {settings.llm_model}")
    print(f"Initial users: {current_users}")

    k6.set_users(current_users, settings.max_users)

    try:
        for interval in range(1, settings.max_intervals + 1):
            snapshot = metrics.collect(current_users)
            decision = engine.decide(snapshot)
            explanation = llm.explain_decision(
                snapshot=snapshot,
                decision=decision,
                thresholds=settings.thresholds(),
            )

            print(
                f"[{interval}/{settings.max_intervals}] "
                f"users={snapshot.users} "
                f"p95={snapshot.latency_p95_ms:.1f}ms "
                f"errors={snapshot.error_rate:.3%} "
                f"cpu={snapshot.cpu_percent:.1f}% "
                f"rps={snapshot.rps:.1f} "
                f"action={decision.action}->{decision.target_users} "
                f"bottleneck={decision.bottleneck}"
            )
            print(explanation)

            if decision.target_users != current_users:
                k6.set_users(decision.target_users, settings.max_users)
                current_users = decision.target_users

            time.sleep(settings.interval_seconds)
    except KeyboardInterrupt:
        print("Controller interrupted; generating final LLM report.")
    finally:
        if engine.history:
            write_report(settings, llm, engine)

    return 0


def write_report(settings: Settings, llm: LLMExplainer, engine: DecisionEngine) -> None:
    summary = engine.summary()
    report = llm.summarize_run(history=engine.history, summary=summary)
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = settings.report_dir / f"alg_report_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Final report written to {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
