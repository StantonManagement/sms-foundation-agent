from __future__ import annotations

import asyncio
import json
from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.adapters.twilio_client import TwilioClient, TwilioError
from src.db.models import SmsMessage
from src.main import create_app
from src.services.sms_outbound import SmsOutboundService


class _FlakyTwilio(TwilioClient):
    def __init__(self, fail_then_succeed: int = 1):  # type: ignore[no-untyped-def]
        self._calls = 0
        self._fail_then = fail_then_succeed

    async def send_sms(self, to: str, body: str, *, from_number: Optional[str] = None) -> str:  # type: ignore[override]
        self._calls += 1
        if self._calls <= self._fail_then:
            raise TwilioError("transient boom", status_code=500, category="transient")
        return "SM-OK"


class _PermanentFailTwilio:
    async def send_sms(self, to: str, body: str, *, from_number: Optional[str] = None) -> str:  # type: ignore[override]
        raise TwilioError("bad request", status_code=400, category="permanent")


@pytest.mark.asyncio
async def test_transient_then_success_retries(async_session, monkeypatch):
    # Make sleep deterministic and quick
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    # Also remove jitter randomness
    import src.utils.retry as retry_mod

    monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: b)

    svc = SmsOutboundService(async_session, _FlakyTwilio(fail_then_succeed=1))
    result = await svc.send("+15555550101", "Hello", request_id="r-1")
    assert result.twilio_sid == "SM-OK"

    # DB updated to queued and has SID
    row = (
        await async_session.execute(select(SmsMessage).where(SmsMessage.id == int(result.id)))
    ).scalar_one()
    assert row.delivery_status in ("queued", "sent")
    assert row.twilio_sid == "SM-OK"
    # One retry implies one sleep
    assert len(sleeps) == 1
    assert 0 <= sleeps[0] <= 2.0


@pytest.mark.asyncio
async def test_permanent_error_no_retries_returns_api_error(monkeypatch):
    app = create_app()

    # Override Twilio client dependency to use the permanent failing client
    from src.api import sms as sms_api
    from src.db.base import get_session as real_get_session

    def _override_client():
        return _PermanentFailTwilio()  # type: ignore[return-value]

    app.dependency_overrides[sms_api.get_twilio_client] = _override_client

    # Provide an in-memory DB session with schema setup
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from src.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with maker() as s:  # type: ignore[misc]
            yield s

    app.dependency_overrides[real_get_session] = _override_session

    async with AsyncClient(transport=None, app=app, base_url="http://testserver") as client:
        resp = await client.post(
            "/sms/send",
            json={"to": "+15555550123", "body": "Hi"},
        )
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "sms.external_failed"
    assert data["error"].get("request_id") is not None


@pytest.mark.asyncio
async def test_429_retry_after_respected(async_session, monkeypatch):
    # Deterministic jitter
    import src.utils.retry as retry_mod

    monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: b)

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    class _RateLimitThenOk(TwilioClient):
        def __init__(self):
            self.calls = 0

        async def send_sms(self, to: str, body: str, *, from_number: Optional[str] = None) -> str:  # type: ignore[override]
            self.calls += 1
            if self.calls == 1:
                # Simulate Retry-After of 0.5s
                raise TwilioError(
                    "rate_limited",
                    status_code=429,
                    category="transient",
                    retry_after_ms=500,
                )
            return "SM-123"

    svc = SmsOutboundService(async_session, _RateLimitThenOk())
    result = await svc.send("+15555550999", "Yo", request_id="r-429")
    assert result.twilio_sid == "SM-123"
    # Sleep honored with cap and jitter disabled -> <= 0.5s
    assert sleeps, "expected a sleep call"
    assert 0.0 <= sleeps[0] <= 0.6


@pytest.mark.asyncio
async def test_429_retry_after_larger_than_backoff_uses_provider_hint(async_session, monkeypatch):
    # Deterministic jitter
    import src.utils.retry as retry_mod

    monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: b)

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    class _RateLimitBigHint(TwilioClient):
        def __init__(self):
            self.calls = 0

        async def send_sms(self, to: str, body: str, *, from_number: Optional[str] = None) -> str:  # type: ignore[override]
            self.calls += 1
            if self.calls == 1:
                # Provider suggests 1.5s which is larger than computed (100ms)
                raise TwilioError(
                    "rate_limited",
                    status_code=429,
                    category="transient",
                    retry_after_ms=1500,
                )
            return "SM-456"

    svc = SmsOutboundService(async_session, _RateLimitBigHint())
    result = await svc.send("+15555550888", "Yo", request_id="r-429b")
    assert result.twilio_sid == "SM-456"
    # Expect sleep close to provider hint (1.5s), jitter disabled -> exact upper bound
    assert sleeps, "expected a sleep call"
    assert 1.4 <= sleeps[0] <= 1.6


@pytest.mark.asyncio
async def test_permanent_failure_emits_labeled_metric(async_session, monkeypatch):
    # Capture metric increments
    from src.adapters.metrics import Metrics

    captured: list[tuple[str, dict]] = []

    def fake_inc(name: str, **labels):
        captured.append((name, labels))

    monkeypatch.setattr(Metrics, "inc", staticmethod(fake_inc))

    class _PermanentFailTwilio2:
        async def send_sms(self, to: str, body: str, *, from_number: Optional[str] = None) -> str:  # type: ignore[override]
            raise TwilioError("bad request", status_code=400, category="permanent")

    svc = SmsOutboundService(async_session, _PermanentFailTwilio2())
    with pytest.raises(TwilioError):
        await svc.send("+15555550777", "Hi", request_id="r-perm")

    # Verify labeled metric for permanent failure
    assert any(
        name == "outbound_sms_failed"
        and labels.get("category") == "permanent"
        and labels.get("route") == "/sms/send"
        and labels.get("status_code") == 400
        for name, labels in captured
    ), f"missing labeled permanent metric in: {captured}"


@pytest.mark.asyncio
async def test_transient_exhaustion_emits_labeled_metric(async_session, monkeypatch):
    # Make sleep fast and deterministic
    async def _fast_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)
    import src.utils.retry as retry_mod

    monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: b)

    # Configure minimal retries
    import types
    from src.utils import config as cfg

    class _TestSettings:
        twilio_send_max_retries = 1
        twilio_send_base_backoff_ms = 10
        twilio_send_backoff_cap_ms = 20

    monkeypatch.setattr(cfg, "get_settings", lambda: _TestSettings())

    # Capture metrics
    from src.adapters.metrics import Metrics

    captured: list[tuple[str, dict]] = []

    def fake_inc(name: str, **labels):
        captured.append((name, labels))

    monkeypatch.setattr(Metrics, "inc", staticmethod(fake_inc))

    class _AlwaysTransient:
        async def send_sms(self, to: str, body: str, *, from_number: Optional[str] = None) -> str:  # type: ignore[override]
            raise TwilioError("oops", status_code=503, category="transient")

    svc = SmsOutboundService(async_session, _AlwaysTransient())
    with pytest.raises(TwilioError):
        await svc.send("+15555550666", "Yo", request_id="r-transient")

    assert any(
        name == "outbound_sms_failed"
        and labels.get("category") == "exhausted"
        and labels.get("route") == "/sms/send"
        and labels.get("status_code") == 503
        for name, labels in captured
    ), f"missing labeled exhausted metric in: {captured}"
