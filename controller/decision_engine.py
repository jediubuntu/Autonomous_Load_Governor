from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass(frozen=True)
class MetricsSnapshot:
    users: int
    latency_p95_ms: float
    error_rate: float
    system_cpu_percent: float
    process_cpu_percent: float
    rps: float
    timestamp: float

    @classmethod
    def now(
        cls,
        users: int,
        latency_p95_ms: float,
        error_rate: float,
        system_cpu_percent: float,
        process_cpu_percent: float,
        rps: float,
    ) -> "MetricsSnapshot":
        return cls(
            users=users,
            latency_p95_ms=latency_p95_ms,
            error_rate=error_rate,
            system_cpu_percent=system_cpu_percent,
            process_cpu_percent=process_cpu_percent,
            rps=rps,
            timestamp=time(),
        )


@dataclass(frozen=True)
class Decision:
    action: str
    target_users: int
    reason: str
    bottleneck: str
    stable: bool
    breakpoint_detected: bool


@dataclass(frozen=True)
class EngineSummary:
    max_stable_users: int
    breakpoint_users: int | None
    bottleneck: str


class DecisionEngine:
    def __init__(
        self,
        *,
        min_users: int,
        max_users: int,
        step_users: int,
        latency_threshold_ms: float,
        error_rate_threshold: float,
        cpu_threshold_percent: float,
        stable_intervals: int,
        knee_latency_multiplier: float,
    ) -> None:
        self.min_users = min_users
        self.max_users = max_users
        self.step_users = step_users
        self.latency_threshold_ms = latency_threshold_ms
        self.error_rate_threshold = error_rate_threshold
        self.cpu_threshold_percent = cpu_threshold_percent
        self.stable_intervals = stable_intervals
        self.knee_latency_multiplier = knee_latency_multiplier
        self.history: list[MetricsSnapshot] = []
        self.max_stable_users = 0
        self.breakpoint_users: int | None = None
        self.bottleneck = "undetermined"

    def register(self, snapshot: MetricsSnapshot, decision: Decision) -> Decision:
        stable = self._is_stable(snapshot)

        normalized = Decision(
            action=decision.action,
            target_users=max(self.min_users, min(self.max_users, decision.target_users)),
            reason=decision.reason,
            bottleneck=decision.bottleneck,
            stable=stable,
            breakpoint_detected=decision.breakpoint_detected,
        )

        self.history.append(snapshot)

        if stable:
            self.max_stable_users = max(self.max_stable_users, snapshot.users)

        if normalized.breakpoint_detected and self.breakpoint_users is None:
            self.breakpoint_users = snapshot.users
            self.bottleneck = normalized.bottleneck

        return normalized

    def summary(self) -> EngineSummary:
        return EngineSummary(
            max_stable_users=self.max_stable_users,
            breakpoint_users=self.breakpoint_users,
            bottleneck=self.bottleneck,
        )

    def _is_stable(self, snapshot: MetricsSnapshot) -> bool:
        return (
            snapshot.latency_p95_ms <= self.latency_threshold_ms
            and snapshot.error_rate <= self.error_rate_threshold
            and snapshot.process_cpu_percent < self.cpu_threshold_percent
        )
