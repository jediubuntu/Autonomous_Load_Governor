from __future__ import annotations

import json
from urllib.request import Request, urlopen


class K6Client:
    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def set_users(self, users: int, max_users: int) -> None:
        payload = {
            "data": {
                "type": "status",
                "attributes": {
                    "vus": users,
                    "vus-max": max(max_users, users),
                },
            }
        }
        self._request("PATCH", "/v1/status", payload)

    def get_status(self) -> dict:
        return self._request("GET", "/v1/status")

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
