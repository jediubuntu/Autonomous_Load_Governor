from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from time import time


@dataclass(frozen=True)
class MetricsSnapshot:
    users: int
    latency_p95_ms: float
    error_rate: float
    cpu_percent: float
    rps: float
    timestamp: float

    @classmethod
    def now(
        cls,
        users: int,
        latency_p95_ms: float,
        error_rate: float,
        cpu_percent: float,
        rps: float,
    ) -> "MetricsSnapshot":
        return cls(
            users=users,
            latency_p95_ms=latency_p95_ms,
            error_rate=error_rate,
            cpu_percent=cpu_percent,
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
        self.stable_streak = 0
        self.max_stable_users = 0
        self.breakpoint_users: int | None = None
        self.bottleneck = "undetermined"

    def decide(self, snapshot: MetricsSnapshot) -> Decision:
        stable = self._is_stable(snapshot)
        if stable:
            self.stable_streak += 1
            self.max_stable_users = max(self.max_stable_users, snapshot.users)
        else:
            self.stable_streak = 0

        target_users = snapshot.users
        action = "hold"
        reason = "waiting for a longer stability window"
        bottleneck = "none"
        breakpoint_detected = False

        if snapshot.error_rate > self.error_rate_threshold:
            action = "decrease"
            bottleneck = "error saturation"
            reason = "error rate exceeded threshold"
            breakpoint_detected = True
            target_users = self._decrease(snapshot.users)
        elif (
            snapshot.latency_p95_ms > self.latency_threshold_ms
            and snapshot.cpu_percent >= self.cpu_threshold_percent
        ):
            action = "decrease"
            bottleneck = "CPU saturation"
            reason = "latency and CPU exceeded thresholds together"
            breakpoint_detected = True
            target_users = self._decrease(snapshot.users)
        elif self._latency_knee_detected(snapshot):
            action = "decrease"
            bottleneck = "latency collapse"
            reason = "p95 latency jumped relative to the recent stable baseline"
            breakpoint_detected = True
            target_users = self._decrease(snapshot.users)
        elif stable and self.stable_streak >= self.stable_intervals:
            action = "increase"
            bottleneck = "none"
            reason = "stable window reached"
            target_users = self._increase(snapshot.users)
            self.stable_streak = 0

        if breakpoint_detected:
            self.breakpoint_users = snapshot.users
            self.bottleneck = bottleneck

        self.history.append(snapshot)
        return Decision(
            action=action,
            target_users=target_users,
            reason=reason,
            bottleneck=bottleneck,
            stable=stable,
            breakpoint_detected=breakpoint_detected,
        )

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
            and snapshot.cpu_percent < self.cpu_threshold_percent
        )

    def _latency_knee_detected(self, snapshot: MetricsSnapshot) -> bool:
        stable_latencies = [
            item.latency_p95_ms
            for item in self.history[-5:]
            if self._is_stable(item) and item.latency_p95_ms > 0
        ]
        if len(stable_latencies) < 2:
            return False
        baseline = median(stable_latencies)
        return snapshot.latency_p95_ms > baseline * self.knee_latency_multiplier

    def _increase(self, users: int) -> int:
        return min(self.max_users, users + self.step_users)

    def _decrease(self, users: int) -> int:
        return max(self.min_users, users - self.step_users)
