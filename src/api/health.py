from __future__ import annotations

import uuid
from typing import Any, Literal
from typing_extensions import TypedDict

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.utils.config import Settings, get_settings


logger = structlog.get_logger(__name__)
router = APIRouter()


class HealthChecks(TypedDict, total=False):
    config: bool
    db: bool | Literal["unknown"]


class HealthResponse(BaseModel):
    ok: bool
    version: str
    checks: HealthChecks


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return basic service health.

    - Confirms config loads
    - Exposes app version
    - Includes optional DB probe flag (unknown by default)
    """
    request_id = str(uuid.uuid4())

    checks: HealthChecks = {
        "config": True,  # settings loaded if we are here
        "db": "unknown",  # non-blocking; no DB wiring in this story
    }
    payload: dict[str, Any] = {
        "ok": True,
        "version": settings.app_version,
        "checks": checks,
    }

    logger.info("health_check", request_id=request_id, **payload)
    return HealthResponse(**payload)
