import asyncio

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Same as api/main.py: backend/.env wins over machine-wide variables.
load_dotenv(override=True)

import models  # noqa: F401  required to load models
from db.base import Base
from db.session import ASYNC_DATABASE_URL as database_url  # validated there
from services.json_logging import configure_logging

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

configure_logging()

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit the migration SQL without connecting to a database."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations over the app's asyncpg URL."""
    connectable = create_async_engine(database_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
