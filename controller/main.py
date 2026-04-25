from __future__ import annotations

from gevent import monkey

monkey.patch_all()

import sys
from pathlib import Path
from time import monotonic

import gevent

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controller.config import ConfigError, Settings
from controller.decision_engine import Decision, DecisionEngine
from controller.reporting import utc_timestamp, write_html_report, write_text_report
from llm.explainer import LLMError, LLMExplainer


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
    print(f"LLM control loop: every {settings.interval_seconds}s")
    print(f"LLM report cadence: every {settings.report_every_seconds}s")

    load_driver.start(current_users)

    llm_failed = False
    decisions: list[Decision] = []
    last_report_time = monotonic()
    try:
        for interval in range(1, settings.max_intervals + 1):
            gevent.sleep(settings.interval_seconds)
            snapshot = load_driver.collect(current_users)

            try:
                llm_decision = llm.decide_next_action(
                    current_users=current_users,
                    snapshot=snapshot,
                    history=engine.history,
                    decisions=decisions,
                    thresholds=settings.thresholds(),
                    min_users=settings.min_users,
                    max_users=settings.max_users,
                    step_users=settings.step_users,
                )
            except LLMError as exc:
                llm_failed = True
                print(f"LLM error: {exc}", file=sys.stderr)
                print("Continuing with fallback hold decision for this interval.", file=sys.stderr)
                llm_decision = Decision(
                    action="hold",
                    target_users=current_users,
                    reason=f"Fallback hold due to LLM error: {exc}",
                    bottleneck="none",
                    stable=False,
                    breakpoint_detected=False,
                )

            decision = engine.register(snapshot, llm_decision)
            decisions.append(decision)

            print(
                f"[{interval}/{settings.max_intervals}] "
                f"users={snapshot.users} "
                f"p95={snapshot.latency_p95_ms:.1f}ms "
                f"errors={snapshot.error_rate:.3%} "
                f"system_cpu={snapshot.system_cpu_percent:.1f}% "
                f"app_cpu={snapshot.process_cpu_percent:.1f}% "
                f"rps={snapshot.rps:.1f} "
                f"action={decision.action}->{decision.target_users} "
                f"bottleneck={decision.bottleneck} "
                f"reason={decision.reason}"
            )

            write_live_report(
                settings=settings,
                engine=engine,
                decisions=decisions,
                interval=interval,
                max_intervals=settings.max_intervals,
            )

            elapsed_since_report = monotonic() - last_report_time
            should_report = elapsed_since_report >= settings.report_every_seconds
            is_last_interval = interval == settings.max_intervals
            if should_report or is_last_interval:
                try:
                    write_report(
                        settings=settings,
                        llm=llm,
                        engine=engine,
                        decisions=decisions,
                        title="ALG Periodic Performance Report",
                    )
                    last_report_time = monotonic()
                except LLMError as exc:
                    llm_failed = True
                    print(f"LLM error: {exc}", file=sys.stderr)
                    print("Skipping periodic LLM report for now and continuing the run.", file=sys.stderr)

            if decision.target_users != current_users:
                load_driver.scale(decision.target_users)
                current_users = decision.target_users
    except KeyboardInterrupt:
        print("Controller interrupted; generating final LLM report.")
    finally:
        load_driver.stop()
        if llm_failed:
            print("Run completed with one or more LLM failures handled by fallback logic.", file=sys.stderr)

    return 0


def write_live_report(
    *,
    settings: Settings,
    engine: DecisionEngine,
    decisions: list[Decision],
    interval: int,
    max_intervals: int,
) -> None:
    summary = engine.summary()
    latest = engine.history[-1]
    latest_decision = decisions[-1]
    report = (
        f"Live report snapshot\n\n"
        f"Interval: {interval}/{max_intervals}\n"
        f"Users: {latest.users}\n"
        f"P95 latency: {latest.latency_p95_ms:.1f} ms\n"
        f"Error rate: {latest.error_rate:.3%}\n"
        f"System CPU: {latest.system_cpu_percent:.1f}%\n"
        f"App process CPU: {latest.process_cpu_percent:.1f}%\n"
        f"RPS: {latest.rps:.1f}\n"
        f"Latest action: {latest_decision.action}->{latest_decision.target_users}\n"
        f"Decision reason: {latest_decision.reason}\n"
        f"Bottleneck: {latest_decision.bottleneck}\n\n"
        f"Scaling control is LLM-directed every interval. "
        f"Periodic summary cadence remains {settings.report_every_seconds}s."
    )
    timestamp = utc_timestamp()
    html_path = write_html_report(
        settings.report_dir,
        report=report,
        history=engine.history,
        decisions=decisions,
        summary=summary,
        timestamp=timestamp,
        title="ALG Live Report",
    )
    print(f"Live HTML report updated at {html_path}")


def write_report(
    *,
    settings: Settings,
    llm: LLMExplainer,
    engine: DecisionEngine,
    decisions: list[Decision],
    title: str,
) -> None:
    summary = engine.summary()
    report = llm.summarize_run(
        history=engine.history,
        decisions=decisions,
        summary=summary,
        title=title,
    )
    timestamp = utc_timestamp()
    markdown_path = write_text_report(settings.report_dir, report, timestamp)
    html_path = write_html_report(
        settings.report_dir,
        report=report,
        history=engine.history,
        decisions=decisions,
        summary=summary,
        timestamp=timestamp,
        title=title,
    )
    print(f"Report written to {markdown_path}")
    print(f"HTML report written to {html_path}")


if __name__ == "__main__":
    raise SystemExit(main())
