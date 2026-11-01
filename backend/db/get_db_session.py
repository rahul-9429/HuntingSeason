from typing import AsyncIterator, Iterator

from sqlalchemy.ext.asyncio import AsyncSession

# from sqlalchemy.orm import Session

from .session import AsyncSessionLocal  # ,SessionLocal


async def get_async_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


# def get_db() -> Iterator[Session]:
#     with SessionLocal() as session:
#         yield session
