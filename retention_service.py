"""Executable HTTP boundary for the field-service retention migration."""

from fastapi import FastAPI, HTTPException

from fieldservice_retention import CutoverResult, RetentionRequest, cut_over_retention
from infrai_client import InfraiClient, InfraiError


app = FastAPI(title="Field-service retention")


@app.post("/retention/cutover", response_model=CutoverResult)
def configure_retention(request: RetentionRequest) -> CutoverResult:
    client = InfraiClient()
    try:
        return cut_over_retention(request, client)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc
    finally:
        client.close()
