from __future__ import annotations

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.session import AsyncSessionLocal


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_anthropic() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
