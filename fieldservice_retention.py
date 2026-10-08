"""Retention policy and migration orchestration for field-service records."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field, HttpUrl, field_validator


class RetentionRequest(BaseModel):
    bucket: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{2,62}$")
    photo_days: int = Field(default=30, ge=1, le=365)
    dispatch_days: int = Field(default=7, ge=1, le=90)
    follow_up_days: int = Field(default=90, ge=1, le=730)
    sweep_url: HttpUrl
    sweep_cron: str = "15 2 * * *"

    @field_validator("sweep_cron")
    @classmethod
    def require_five_cron_fields(cls, value: str) -> str:
        if len(value.split()) != 5:
            raise ValueError("sweep_cron must contain five fields")
        return value


class CutoverResult(BaseModel):
    bucket: str
    lifecycle_rules: int
    scheduled_job: str
    status: str


class RetentionClient(Protocol):
    def create_bucket(self, name: str) -> dict[str, Any]:
        """Provision the retention bucket."""

    def set_lifecycle(
        self, bucket: str, rules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Replace the bucket lifecycle policy."""

    def schedule_sweep(self, cron_expr: str, task: str) -> str:
        """Register the sweep and return its identifier."""


def lifecycle_rules(request: RetentionRequest) -> list[dict[str, Any]]:
    """Translate field-service record classes into independent expiry rules."""
    return [
        {
            "prefix": "work-orders/photos/",
            "expire_days": request.photo_days,
        },
        {
            "prefix": "dispatch/status/",
            "expire_days": request.dispatch_days,
        },
        {
            "prefix": "technicians/follow-up/",
            "expire_days": request.follow_up_days,
        },
    ]


def cut_over_retention(
    request: RetentionRequest, infrai: RetentionClient
) -> CutoverResult:
    rules = lifecycle_rules(request)
    infrai.create_bucket(request.bucket)
    infrai.set_lifecycle(request.bucket, rules)
    job_id = infrai.schedule_sweep(request.sweep_cron, str(request.sweep_url))
    return CutoverResult(
        bucket=request.bucket,
        lifecycle_rules=len(rules),
        scheduled_job=job_id,
        status="ready-for-cutover",
    )
