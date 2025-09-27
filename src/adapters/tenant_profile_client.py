from __future__ import annotations

import asyncio
from typing import Optional

import httpx


class TenantProfileClient:
    """Client to update tenant language preferences.

    Contract (idempotent): PUT {base}/tenants/{tenant_id}/language {"language": "en|es|pt"}
    - 200/204 => success
    - 404 => noop (treat as success=false but not error)
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

    async def _put(self, client: httpx.AsyncClient, tenant_id: str, lang: str) -> Optional[bool]:
        if not self.base_url:
            return None
        url = f"{self.base_url}/tenants/{tenant_id}/language"
        r = await client.put(url, json={"language": lang})
        if r.status_code in (200, 204):
            return True
        if r.status_code == 404:
            return False
        # Treat other statuses as transient
        r.raise_for_status()
        return False

    async def update_language(self, tenant_id: str, lang: str) -> Optional[bool]:
        """Update tenant language.

        Returns True on success, False on known-noop (e.g., 404), None if base_url not configured
        or retries exhausted due to transient errors.
        """
        if not self.base_url or not tenant_id or not lang or lang == "unknown":
            return None

        attempt = 0
        delay_ms = self.backoff_initial_ms
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            while True:
                attempt += 1
                try:
                    return await self._put(client, tenant_id, lang)
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError):
                    if attempt >= self.max_attempts:
                        return None
                    await asyncio.sleep(delay_ms / 1000.0)
                    delay_ms = min(delay_ms * 2, 2000)

