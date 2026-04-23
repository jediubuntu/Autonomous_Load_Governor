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

    def explain_decision(
        self,
        *,
        snapshot: MetricsSnapshot,
        decision: Decision,
        thresholds: dict[str, float | int],
    ) -> str:
        payload = {
            "metrics": asdict(snapshot),
            "decision": asdict(decision),
            "thresholds": thresholds,
        }
        return self._chat(
            system=(
                "You are ALG's performance test analyst. Use only the supplied metrics. "
                "Explain the controller decision in 3 concise bullets: observation, "
                "likely bottleneck, next action."
            ),
            user=json.dumps(payload, indent=2),
        )

    def summarize_run(
        self,
        *,
        history: list[MetricsSnapshot],
        summary: EngineSummary,
    ) -> str:
        payload = {
            "summary": asdict(summary),
            "history": [asdict(item) for item in history],
        }
        return self._chat(
            system=(
                "You are generating the final Autonomous Load Governor report. "
                "Use markdown. Include max stable users, breakpoint, bottleneck, "
                "evidence, and recommended fixes. Do not invent metrics."
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
        }
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
