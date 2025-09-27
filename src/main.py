from __future__ import annotations

import logging
import sys

import structlog
from fastapi import FastAPI

from src.api.health import router as health_router
from src.api.webhooks.twilio import router as twilio_router
from src.api.conversations import router as conversations_router
from src.api.sms import router as sms_router
from src.utils.config import get_settings


def configure_logging() -> None:
    """Configure structlog for JSON logs with reasonable defaults."""
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            timestamper,
            structlog.processors.add_log_level,
            structlog.processors.EventRenamer("message"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Ensure stdlib logs are forwarded in JSON too
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health_router)
    app.include_router(twilio_router)
    app.include_router(conversations_router)
    app.include_router(sms_router)
    return app


app = create_app()
