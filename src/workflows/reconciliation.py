from __future__ import annotations

from typing import Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.metrics import Metrics
from src.adapters.monitor_client import TenantLookupClient
from src.repositories.conversations import ConversationRepository
from src.services.conversations import ConversationService
from src.utils.config import get_settings
from src.utils.phone import variants


logger = structlog.get_logger(__name__)


async def reconcile_unknown_conversations(
    session_maker: async_sessionmaker[AsyncSession], *, batch_size: int = 100
) -> dict[str, int]:
    """Attempt tenant reconciliation for conversations with no tenant.

    Returns a summary dict with counts of processed/succeeded/no_match.
    """
    settings = get_settings()
    client = TenantLookupClient(settings.monitor_api_url)

    processed = 0
    succeeded = 0
    no_match = 0

    async with session_maker() as session:
        conv_repo = ConversationRepository(session)
        items = await conv_repo.list_unknown(limit=batch_size)
        for conv in items:
            processed += 1
            raw = conv.phone_number_original or conv.phone_number_canonical
            phones = variants(raw)
            try:
                match = await client.lookup(phones)
            except Exception:
                match = None
            if match:
                svc = ConversationService(session)
                applied = await svc.reconcile_tenant(conv.id, match.tenant_id)
                if applied:
                    succeeded += 1
            else:
                Metrics.inc("reconciliation_no_match")
                logger.info(
                    "reconciliation_no_match",
                    conversation_id=conv.id,
                    phone=raw,
                )
                no_match += 1

    return {"processed": processed, "succeeded": succeeded, "no_match": no_match}

