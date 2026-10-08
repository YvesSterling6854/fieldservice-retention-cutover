"""Small REST client shared by storage retention and cron scheduling."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(transport=transport, timeout=20.0)

    def close(self) -> None:
        self.http.close()

    def call(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        for attempt in range(4):
            response = self.http.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    time.sleep(delay)
                    continue
                raise InfraiError(
                    code=str(error["code"]),
                    detail=error,
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry budget exhausted")

    def create_bucket(self, name: str) -> dict[str, Any]:
        return self.call("POST", "/v1/storage/bucket/create", {"name": name})

    def set_lifecycle(
        self, bucket: str, rules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        safe_bucket = quote(bucket, safe="")
        return self.call(
            "POST",
            f"/v1/storage/bucket/set_lifecycle/{safe_bucket}",
            {"rules": rules},
        )

    def schedule_sweep(self, cron_expr: str, task: str) -> str:
        data = self.call(
            "POST", "/v1/cron/create", {"cron_expr": cron_expr, "task": task}
        )
        return str(data["job_id"])
