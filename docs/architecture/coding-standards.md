# Coding Standards

## Core Standards
- Languages & Runtimes: Python 3.11.x; FastAPI; SQLAlchemy 2.x async; Alembic; httpx; twilio.
- Style & Linting: ruff + black + isort; mypy strict on src; JSON logs via structlog.
- Test Organization: pytest with `tests/unit`, `tests/integration`; async tests use `pytest-asyncio`; external HTTP via respx.

## Critical Rules
- Type Sharing: Define DTOs and response models with Pydantic; never return raw dicts from routers.
- Repository Pattern: All DB access through repositories; no inline SQL in routers/services.
- Idempotency: All webhook handlers must guard via unique `twilio_sid`; duplicates return 200 OK no-op.
- Validation: Validate inputs at API boundary; normalize phone numbers with `phonenumbers` before use.
- Logging: Use structlog with request_id and twilio_sid; never log secrets or full PII payloads.
- Background Work: Long-running/external calls use BackgroundTasks; webhook responds fast.
- Errors: Translate internal exceptions to ApiError; do not leak stack traces.
- Config: Centralized settings module; avoid scattered `os.environ` access.
