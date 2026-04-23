from __future__ import annotations

import json
import time
from dataclasses import asdict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from controller.decision_engine import Decision, EngineSummary, MetricsSnapshot


class LLMError(RuntimeError):
    pass


class LLMExplainer:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        max_retries: int = 3,
        retry_seconds: float = 10.0,
        timeout_seconds: int = 45,
    ) -> None:
        if not api_key:
            raise ValueError("LLM API key is required")
        if not model:
            raise ValueError("LLM model is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.retry_seconds = retry_seconds
        self.timeout_seconds = timeout_seconds

    def decide_next_action(
        self,
        *,
        current_users: int,
        snapshot: MetricsSnapshot,
        history: list[MetricsSnapshot],
        decisions: list[Decision],
        thresholds: dict[str, float | int],
        min_users: int,
        max_users: int,
        step_users: int,
    ) -> Decision:
        payload = {
            "current_users": current_users,
            "metrics": asdict(snapshot),
            "recent_history": [asdict(item) for item in history[-5:]],
            "recent_decisions": [asdict(item) for item in decisions[-5:]],
            "thresholds": thresholds,
            "bounds": {
                "min_users": min_users,
                "max_users": max_users,
                "default_step_users": step_users,
            },
        }
        content = self._chat(
            system=(
                "You are ALG's scaling controller. Decide the next load action using ONLY the supplied metrics. "
                "Return strict JSON with keys: action, target_users, reason, bottleneck, breakpoint_detected. "
                "Allowed action values: increase, hold, decrease. "
                "Respect bounds exactly. "
                "Increase users if latency and errors are healthy relative to thresholds. "
                "Decrease only if there is clear instability. "
                "Use bottleneck values from: none, CPU saturation, error saturation, latency collapse. "
                "Do not include markdown fences or extra text."
            ),
            user=json.dumps(payload, indent=2),
        )

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM decision was not valid JSON: {content}") from exc

        action = str(parsed.get("action", "hold")).strip().lower()
        if action not in {"increase", "hold", "decrease"}:
            action = "hold"

        target_users = int(parsed.get("target_users", current_users))
        target_users = max(min_users, min(max_users, target_users))

        if action == "increase" and target_users <= current_users:
            target_users = min(max_users, current_users + step_users)
        elif action == "decrease" and target_users >= current_users:
            target_users = max(min_users, current_users - step_users)
        elif action == "hold":
            target_users = current_users

        bottleneck = str(parsed.get("bottleneck", "none")).strip() or "none"
        if bottleneck not in {"none", "CPU saturation", "error saturation", "latency collapse"}:
            bottleneck = "none"

        return Decision(
            action=action,
            target_users=target_users,
            reason=str(parsed.get("reason", "LLM-directed scaling decision")).strip()
            or "LLM-directed scaling decision",
            bottleneck=bottleneck,
            stable=False,
            breakpoint_detected=bool(parsed.get("breakpoint_detected", action == "decrease" and bottleneck != "none")),
        )

    def summarize_run(
        self,
        *,
        history: list[MetricsSnapshot],
        decisions: list[Decision] | None = None,
        summary: EngineSummary,
        title: str = "Autonomous Load Governor Report",
    ) -> str:
        payload = {
            "title": title,
            "summary": asdict(summary),
            "history": [asdict(item) for item in history],
            "decisions": [asdict(item) for item in decisions or []],
        }
        return self._chat(
            system=(
                "You are generating an Autonomous Load Governor performance report. "
                "Use markdown. Include max stable users, breakpoint, bottleneck, "
                "evidence, and recommended fixes. Do not invent metrics. "
                "Keep it concise and useful for a performance engineering review."
            ),
            user=json.dumps(payload, indent=2),
        )

    def _chat(self, *, system: str, user: str) -> str:
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"} if "strict JSON" in system else None,
        }
        request_body = {key: value for key, value in request_body.items() if value is not None}
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        payload = self._send_with_retries(request)

        try:
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected LLM response shape: {payload}") from exc

    def _send_with_retries(self, request: Request) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                message = self._http_error_message(exc)
                retryable = exc.code in {408, 409, 429, 500, 502, 503, 504}
                if not retryable or attempt >= self.max_retries:
                    raise LLMError(message) from exc
                sleep_seconds = self._retry_after_seconds(exc) or self.retry_seconds
                if exc.code == 429:
                    sleep_seconds = max(120.0, sleep_seconds)
                print(
                    f"LLM request failed with HTTP {exc.code}; "
                    f"retrying in {sleep_seconds:.1f}s ({attempt + 1}/{self.max_retries})"
                )
                time.sleep(sleep_seconds)
            except URLError as exc:
                if attempt >= self.max_retries:
                    raise LLMError(f"LLM request failed: {exc.reason}") from exc
                print(
                    "LLM request failed due to a network error; "
                    f"retrying in {self.retry_seconds:.1f}s ({attempt + 1}/{self.max_retries})"
                )
                time.sleep(self.retry_seconds)

        raise LLMError("LLM request failed after retries")

    def _retry_after_seconds(self, exc: HTTPError) -> float | None:
        retry_after = exc.headers.get("Retry-After")
        if not retry_after:
            return None
        try:
            return max(0.1, float(retry_after))
        except ValueError:
            return None

    def _http_error_message(self, exc: HTTPError) -> str:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""

        if body:
            try:
                payload = json.loads(body)
                detail = payload.get("error", {}).get("message") or body
            except json.JSONDecodeError:
                detail = body
        else:
            detail = exc.reason

        return f"LLM request failed with HTTP {exc.code}: {detail}"
