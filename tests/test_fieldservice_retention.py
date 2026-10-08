from typing import Any

from fastapi.testclient import TestClient

from fieldservice_retention import RetentionRequest, cut_over_retention, lifecycle_rules
from retention_service import app


class RecordingInfrai:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def create_bucket(self, name: str) -> dict[str, Any]:
        self.calls.append(("create_bucket", name))
        return {"name": name}

    def set_lifecycle(
        self, bucket: str, rules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self.calls.append(("set_lifecycle", (bucket, rules)))
        return {"updated": True}

    def schedule_sweep(self, cron_expr: str, task: str) -> str:
        self.calls.append(("schedule_sweep", (cron_expr, task)))
        return "job-field-retention"


def request() -> RetentionRequest:
    return RetentionRequest(
        bucket="fieldservice-archive",
        photo_days=21,
        dispatch_days=3,
        follow_up_days=60,
        sweep_url="https://ops.example.com/jobs/retention-sweep",
    )


def test_business_retention_windows_follow_record_value() -> None:
    rules = lifecycle_rules(request())

    assert rules == [
        {"prefix": "work-orders/photos/", "expire_days": 21},
        {"prefix": "dispatch/status/", "expire_days": 3},
        {"prefix": "technicians/follow-up/", "expire_days": 60},
    ]


def test_cutover_creates_policy_before_scheduling_sweep() -> None:
    infrai = RecordingInfrai()

    result = cut_over_retention(request(), infrai)

    assert result.status == "ready-for-cutover"
    assert result.lifecycle_rules == 3
    assert result.scheduled_job == "job-field-retention"
    assert [name for name, _ in infrai.calls] == [
        "create_bucket",
        "set_lifecycle",
        "schedule_sweep",
    ]


def test_request_rejects_invalid_cron_shape() -> None:
    response = TestClient(app).post(
        "/retention/cutover",
        json={
            "bucket": "fieldservice-archive",
            "sweep_url": "https://ops.example.com/jobs/retention-sweep",
            "sweep_cron": "daily",
        },
    )

    assert response.status_code == 422
