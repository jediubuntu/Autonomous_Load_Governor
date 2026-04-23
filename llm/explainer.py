from __future__ import annotations

import json
from dataclasses import asdict
from urllib.request import Request, urlopen

from controller.decision_engine import Decision, EngineSummary, MetricsSnapshot


class LLMExplainer:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 45,
    ) -> None:
        if not api_key:
            raise ValueError("LLM API key is required")
        if not model:
            raise ValueError("LLM model is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
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
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        try:
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected LLM response shape: {payload}") from exc
