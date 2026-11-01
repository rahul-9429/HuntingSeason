import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

__DEV__ = os.getenv("ENV") != "production"


def _database_url() -> URL:
    try:
        url = make_url(os.getenv("DATABASE_URL", ""))
    except ArgumentError:
        url = None
    if url is None or url.drivername.split("+")[0] not in ("postgres", "postgresql"):
        raise RuntimeError(
            "DATABASE_URL must be set to a Postgres URL: postgresql://user:password@host:5432/dbname"
        )
    return url


def _with_driver(url: URL, driver: str) -> URL:
    query = dict(url.query)
    ssl = [query.pop(key) for key in ("ssl", "sslmode") if key in query]
    channel_binding = query.pop("channel_binding", None)
    if ssl:
        query["ssl" if driver == "asyncpg" else "sslmode"] = ssl[0]
    if channel_binding and driver != "asyncpg":
        query["channel_binding"] = channel_binding
    return url.set(drivername=f"postgresql+{driver}", query=query)


_url = _database_url()
ASYNC_DATABASE_URL = _with_driver(_url, "asyncpg")
# SYNC_DATABASE_URL = _with_driver(_url, "psycopg")

_pool_options = dict(
    pool_size=10 if __DEV__ else 30,
    max_overflow=20 if __DEV__ else 40,
    pool_recycle=300,
    pool_pre_ping=True,
    pool_timeout=30,
)

async_engine = create_async_engine(ASYNC_DATABASE_URL, **_pool_options)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# sync_engine = create_engine(SYNC_DATABASE_URL, **_pool_options)
# SessionLocal = sessionmaker(sync_engine, expire_on_commit=False)
