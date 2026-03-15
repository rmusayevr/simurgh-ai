"""
Alembic migration environment configuration.

Supports both sync (offline) and async (online) migration modes.
Automatically imports all models to ensure complete schema generation.
"""

import asyncio
import asyncpg
import logging
import os

from logging.config import fileConfig
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from alembic import context

# ==================== Import All Models ====================
# Importing the package ensures ALL models are registered
import app.models  # noqa: F401

logger = logging.getLogger("alembic.env")

# ==================== Alembic Config ====================

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


# ==================== Database URL ====================


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")

    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is not set.\n"
            "Make sure your .env file is loaded before running migrations.\n"
            "Example: DATABASE_URL=postgresql://user:pass@localhost:5432/dbname"
        )

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url


def get_sync_database_url() -> str:
    return get_database_url().replace("+asyncpg", "")


# ==================== Migration Helpers ====================


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        if name.startswith("spatial_ref_sys"):
            return False
        if name.startswith("pg_"):
            return False
    return True


def compare_type(
    context, inspected_column, metadata_column, inspected_type, metadata_type
):
    return None


# ==================== Migration Modes ====================


def run_migrations_offline() -> None:
    url = get_sync_database_url()

    logger.info("Running migrations in OFFLINE mode")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = get_database_url()

    logger.info("Running migrations in ONLINE mode")
    logger.info(f"Database: {url.split('@')[-1]}")

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        echo=False,
    )

    try:
        async with connectable.connect() as connection:
            # Enable required extensions
            for ext in ["vector", "pg_trgm"]:
                try:
                    await connection.execute(
                        text(f"CREATE EXTENSION IF NOT EXISTS {ext}")
                    )
                except ProgrammingError as e:
                    if isinstance(e.orig, asyncpg.exceptions.DuplicateObjectError):
                        logger.warning(f"Extension '{ext}' already exists, skipping.")
                    else:
                        raise

            await connection.run_sync(do_run_migrations)

            await connection.commit()

        logger.info("Migrations completed successfully and COMMITTED.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await connectable.dispose()


# ==================== Entry Point ====================

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
