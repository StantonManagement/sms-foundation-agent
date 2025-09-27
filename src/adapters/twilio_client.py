from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional

import httpx


class TwilioError(Exception):
    """Raised when Twilio send fails.

    Attributes:
        status_code: HTTP status code when available
        category: 'transient' | 'permanent' | 'exhausted' | None (classification for retry logic)
        correlation_id: Provider correlation/request id when available
        retry_after_ms: Suggested backoff from provider (e.g., 429 Retry-After)
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        category: str | None = None,
        correlation_id: str | None = None,
        retry_after_ms: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.category = category
        self.correlation_id = correlation_id
        self.retry_after_ms = retry_after_ms


@dataclass(frozen=True)
class TwilioConfig:
    account_sid: str
    auth_token: str
    from_number: str


class TwilioClient:
    """Minimal Twilio Messages API client using httpx.

    Uses Basic Auth with Account SID and Auth Token. Sends SMS via REST endpoint and returns MessageSid.
    This is intentionally lightweight to enable mocking in tests without adding heavy SDK deps.
    """

    def __init__(self, config: TwilioConfig, *, timeout_s: float = 5.0):
        self.config = config
        self.timeout_s = timeout_s

    async def send_sms(self, to: str, body: str, *, from_number: Optional[str] = None) -> str:
        from_num = from_number or self.config.from_number
        if not self.config.account_sid or not self.config.auth_token or not from_num:
            raise TwilioError("twilio_not_configured")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.config.account_sid}/Messages.json"
        auth = (self.config.account_sid, self.config.auth_token)
        data = {"To": to, "From": from_num, "Body": body}
        async with httpx.AsyncClient(timeout=self.timeout_s, auth=auth) as client:
            try:
                resp = await client.post(url, data=data)
                if resp.status_code in (200, 201):
                    data = resp.json() if resp.content else {}
                    sid = data.get("sid") or data.get("message_sid")
                    if not sid:
                        raise TwilioError(
                            "missing_sid",
                            status_code=resp.status_code,
                            category="transient",
                            correlation_id=(
                                resp.headers.get("Twilio-Request-Id")
                                or resp.headers.get("X-Request-Id")
                            ),
                        )
                    return str(sid)
                # 4xx/5xx -> classify and raise
                status = resp.status_code
                corr = resp.headers.get("Twilio-Request-Id") or resp.headers.get("X-Request-Id")
                retry_after_ms: int | None = None
                if status == 429:
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        # Retry-After can be seconds or HTTP-date; handle seconds
                        try:
                            secs = int(ra)
                            retry_after_ms = secs * 1000
                        except ValueError:
                            retry_after_ms = None
                category = "transient" if (status >= 500 or status == 429) else "permanent"
                raise TwilioError(
                    f"twilio_error:{status}",
                    status_code=status,
                    category=category,
                    correlation_id=corr,
                    retry_after_ms=retry_after_ms,
                )
            except (httpx.ConnectError, httpx.ReadTimeout) as ex:
                raise TwilioError("twilio_network_error", category="transient") from ex
