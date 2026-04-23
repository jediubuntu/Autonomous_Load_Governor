from __future__ import annotations

from gevent import monkey

monkey.patch_all()

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controller.config import ConfigError, Settings
from controller.decision_engine import DecisionEngine
from llm.explainer import LLMError, LLMExplainer
import gevent


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

    from controller.load_driver import LocustLoadDriver

    load_driver = LocustLoadDriver(
        target_url=settings.target_url,
        spawn_rate=settings.spawn_rate,
    )
    llm = LLMExplainer(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_retries=settings.llm_max_retries,
        retry_seconds=settings.llm_retry_seconds,
    )
    engine = build_engine(settings)

    current_users = settings.initial_users
    print("Starting ALG controller")
    print(f"Target: {settings.target_url}")
    print("Load driver: Locust")
    print(f"LLM model: {settings.llm_model}")
    print(f"Initial users: {current_users}")

    load_driver.start(current_users)

    llm_failed = False
    try:
        for interval in range(1, settings.max_intervals + 1):
            gevent.sleep(settings.interval_seconds)
            snapshot = load_driver.collect(current_users)
            decision = engine.decide(snapshot)

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

            try:
                explanation = llm.explain_decision(
                    snapshot=snapshot,
                    decision=decision,
                    thresholds=settings.thresholds(),
                )
                print(explanation)
            except LLMError as exc:
                llm_failed = True
                print(f"LLM error: {exc}", file=sys.stderr)
                print("Stopping run because LLM explanations are required.", file=sys.stderr)
                break

            if decision.target_users != current_users:
                load_driver.scale(decision.target_users)
                current_users = decision.target_users
    except KeyboardInterrupt:
        print("Controller interrupted; generating final LLM report.")
    finally:
        load_driver.stop()
        if engine.history and not llm_failed:
            write_report(settings, llm, engine)
        elif llm_failed:
            print("Final report skipped because the LLM request failed.", file=sys.stderr)

    return 0


def write_report(settings: Settings, llm: LLMExplainer, engine: DecisionEngine) -> None:
    summary = engine.summary()
    try:
        report = llm.summarize_run(history=engine.history, summary=summary)
    except LLMError as exc:
        print(f"Final report failed: {exc}", file=sys.stderr)
        return
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = settings.report_dir / f"alg_report_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Final report written to {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
