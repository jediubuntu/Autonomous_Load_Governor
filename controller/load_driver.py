from __future__ import annotations

import json
from urllib.request import urlopen

from locust.env import Environment

from controller.decision_engine import MetricsSnapshot
from load.locustfile import AlgUser


class LocustLoadDriver:
    def __init__(
        self,
        *,
        target_url: str,
        spawn_rate: float,
        timeout_seconds: int = 5,
    ) -> None:
        self.target_url = target_url.rstrip("/")
        self.spawn_rate = spawn_rate
        self.timeout_seconds = timeout_seconds
        self.environment = Environment(user_classes=[AlgUser], host=self.target_url)
        self.runner = self.environment.create_local_runner()

    def start(self, users: int) -> None:
        self.runner.start(user_count=users, spawn_rate=self.spawn_rate)

    def scale(self, users: int) -> None:
        self.runner.start(user_count=users, spawn_rate=self.spawn_rate)

    def collect(self, users: int) -> MetricsSnapshot:
        total = self.environment.stats.total
        request_count = max(total.num_requests, 0)
        failure_count = max(total.num_failures, 0)
        error_rate = failure_count / request_count if request_count else 0.0
        latency_p95_ms = float(total.get_response_time_percentile(0.95) or 0.0)
        rps = float(getattr(total, "current_rps", 0.0) or getattr(total, "total_rps", 0.0) or 0.0)

        snapshot = MetricsSnapshot.now(
            users=users,
            latency_p95_ms=latency_p95_ms,
            error_rate=error_rate,
            cpu_percent=self._read_cpu_percent(),
            rps=rps,
        )
        self.environment.stats.reset_all()
        return snapshot

    def stop(self) -> None:
        self.runner.quit()

    def _read_cpu_percent(self) -> float:
        try:
            with urlopen(f"{self.target_url}/runtime", timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return float(payload.get("cpu_percent", 0.0))
        except Exception:
            return 0.0
