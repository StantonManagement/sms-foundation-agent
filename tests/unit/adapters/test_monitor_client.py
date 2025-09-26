import pytest
import respx
from httpx import Response

from src.adapters.monitor_client import TenantLookupClient


@pytest.mark.asyncio
@respx.mock
async def test_lookup_success_first_variant():
    base = "https://monitor.example.com"
    respx.get(f"{base}/tenants/lookup").mock(
        return_value=Response(200, json={"tenant_id": "t-123"})
    )
    client = TenantLookupClient(base)
    match = await client.lookup(["+14155551212", "4155551212"])
    assert match is not None and match.tenant_id == "t-123"


@pytest.mark.asyncio
@respx.mock
async def test_lookup_not_found_404():
    base = "https://monitor.example.com"
    respx.get(f"{base}/tenants/lookup").mock(return_value=Response(404))
    client = TenantLookupClient(base)
    match = await client.lookup(["+19999999999"]) 
    assert match is None


@pytest.mark.asyncio
@respx.mock
async def test_lookup_retries_on_5xx_then_succeeds():
    base = "https://monitor.example.com"
    route = respx.get(f"{base}/tenants/lookup")
    route.side_effect = [
        Response(500),
        Response(502),
        Response(200, json={"tenant_id": "ok"}),
    ]
    client = TenantLookupClient(base, max_attempts=5, backoff_initial_ms=1)
    match = await client.lookup(["+14155551212"]) 
    assert match is not None and match.tenant_id == "ok"

