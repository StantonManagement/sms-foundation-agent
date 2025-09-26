import pytest
from httpx import AsyncClient

from src.main import create_app


@pytest.mark.asyncio
async def test_get_conversation_404(async_session):
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/conversations/14155550000")
        assert resp.status_code == 404

