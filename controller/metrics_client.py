from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from controller.decision_engine import MetricsSnapshot


LATENCY_P95_QUERY = (
    'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{path="/work"}[1m])) '
    "by (le)) * 1000 or vector(0)"
)
ERROR_RATE_QUERY = (
    'sum(rate(http_requests_total{path="/work",status=~"5.."}[1m])) / '
    'clamp_min(sum(rate(http_requests_total{path="/work"}[1m])), 0.001) or vector(0)'
)
CPU_QUERY = "avg_over_time(alg_app_cpu_percent[1m]) or vector(0)"
RPS_QUERY = 'sum(rate(http_requests_total{path="/work"}[1m])) or vector(0)'


class PrometheusMetricsClient:
    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def collect(self, users: int) -> MetricsSnapshot:
        return MetricsSnapshot.now(
            users=users,
            latency_p95_ms=self.query_scalar(LATENCY_P95_QUERY),
            error_rate=self.query_scalar(ERROR_RATE_QUERY),
            cpu_percent=self.query_scalar(CPU_QUERY),
            rps=self.query_scalar(RPS_QUERY),
        )

    def query_scalar(self, query: str) -> float:
        url = f"{self.base_url}/api/v1/query?{urlencode({'query': query})}"
        request = Request(url, method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if payload.get("status") != "success":
            raise RuntimeError(f"Prometheus query failed: {payload}")

        result = payload.get("data", {}).get("result", [])
        if not result:
            return 0.0

        value = result[0].get("value", [None, "0"])[1]
        return float(value)
