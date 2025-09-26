from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, Optional

import httpx


@dataclass(frozen=True)
class TenantMatch:
    tenant_id: str


class TenantLookupClient:
    """Client for Collections Monitor tenant lookup by phone variants.

    Minimal contract: GET {base_url}/tenants/lookup?phone={value}
    - 200 JSON with {"tenant_id": "..."} => match
    - 404 or 204/empty => no match
    - 5xx/timeouts => retry with backoff up to max_attempts
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 3.0,
        max_attempts: int = 4,
        backoff_initial_ms: int = 100,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_attempts = max(1, max_attempts)
        self.backoff_initial_ms = max(1, backoff_initial_ms)

    async def _get(self, client: httpx.AsyncClient, phone: str) -> Optional[TenantMatch]:
        url = f"{self.base_url}/tenants/lookup"
        r = await client.get(url, params={"phone": phone})
        if r.status_code == 200:
            data = r.json() if r.content else None
            if isinstance(data, dict) and data.get("tenant_id"):
                return TenantMatch(tenant_id=str(data["tenant_id"]))
            return None
        if r.status_code in (404, 204):
            return None
        # Treat other statuses as transient
        r.raise_for_status()
        return None

    async def lookup(self, variants: Iterable[str]) -> Optional[TenantMatch]:
        # If not configured, skip
        if not self.base_url:
            return None

        attempt = 0
        delay_ms = self.backoff_initial_ms
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            while True:
                attempt += 1
                try:
                    # Try each variant in order for this attempt
                    for v in variants:
                        if not v:
                            continue
                        match = await self._get(client, v)
                        if match:
                            return match
                    # No variant matched; no more work to do
                    return None
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError):
                    if attempt >= self.max_attempts:
                        return None
                    await asyncio.sleep(delay_ms / 1000.0)
                    delay_ms = min(delay_ms * 2, 2000)

