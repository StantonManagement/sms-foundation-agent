import pytest
import respx
from httpx import Response

from src.adapters.tenant_profile_client import TenantProfileClient


@pytest.mark.asyncio
@respx.mock
async def test_update_language_success_200():
    base = "https://tenant.example.com"
    tenant_id = "t-123"
    route = respx.put(f"{base}/tenants/{tenant_id}/language").mock(
        return_value=Response(200)
    )
    client = TenantProfileClient(base)
    res = await client.update_language(tenant_id, "es")
    assert res is True
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_update_language_404_noop():
    base = "https://tenant.example.com"
    tenant_id = "t-404"
    route = respx.put(f"{base}/tenants/{tenant_id}/language").mock(
        return_value=Response(404)
    )
    client = TenantProfileClient(base)
    res = await client.update_language(tenant_id, "en")
    assert res is False
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_update_language_retries_then_succeeds():
    base = "https://tenant.example.com"
    tenant_id = "t-500"
    route = respx.put(f"{base}/tenants/{tenant_id}/language")
    route.side_effect = [Response(500), Response(502), Response(204)]
    client = TenantProfileClient(base, max_attempts=5, backoff_initial_ms=1)
    res = await client.update_language(tenant_id, "pt")
    assert res is True
    assert route.called

