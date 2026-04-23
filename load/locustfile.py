from __future__ import annotations

import os

from locust import HttpUser, task


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


class AlgUser(HttpUser):
    def wait_time(self) -> float:
        return max(0.1, _float_env("SLEEP_SECONDS", 1.0))

    @task(2)
    def synthetic_work(self) -> None:
        work_ms = _int_env("WORK_MS", 20)
        fail_pct = _float_env("FAIL_PCT", 0.0)
        self.client.get(
            f"/work?work_ms={work_ms}&fail_pct={fail_pct}",
            name="/work",
        )

    @task(1)
    def crud_flow(self) -> None:
        item_name = f"locust-user-{id(self)}"
        create_response = self.client.post(
            "/items",
            json={
                "name": item_name,
                "description": "created by Locust adaptive flow",
                "price": 10.0,
            },
            name="/items",
        )
        if create_response.status_code != 201:
            return

        item_id = create_response.json().get("id")
        if not item_id:
            return

        self.client.get(f"/items/{item_id}", name="/items/{item_id}")
        self.client.put(
            f"/items/{item_id}",
            json={
                "name": f"{item_name}-updated",
                "description": "updated by Locust adaptive flow",
                "price": 20.0,
            },
            name="/items/{item_id}",
        )
        self.client.delete(f"/items/{item_id}", name="/items/{item_id}")
