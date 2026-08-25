# backend/database/migrations/env.py
#
# CONCEPT: Alembic's env.py — The Migration Environment
#
# This file is Alembic's "brain." It runs every time you run an alembic command.
# It does two critical things:
#
# 1. OFFLINE MODE (run_migrations_offline):
#    Generates SQL without connecting to the DB.
#    Output: a .sql file you can review before running.
#    Use case: Production deployments where a DBA reviews SQL before running.
#
# 2. ONLINE MODE (run_migrations_online):
#    Connects to the DB and runs migrations directly.
#    This is what you use in development: alembic upgrade head
#
# CONCEPT: Why does env.py import your models?
# Alembic's autogenerate feature works by comparing:
#   Current DB schema (what tables/columns exist right now)
#   vs.
#   Your SQLAlchemy metadata (what your Python models say should exist)
#
# To see your models, Alembic must import them. That's why we import Base
# (which has the metadata) AND import all models (so they register themselves
# into Base.metadata).
#
# If you forget to import a new model → Alembic won't detect it → no migration.
#
# CONCEPT: Sync vs Async in Alembic
# Alembic was designed for synchronous SQLAlchemy.
# Our app uses async SQLAlchemy (asyncpg driver).
# But Alembic doesn't support async natively!
#
# Solution: use run_sync() to run synchronous Alembic operations
# within an async connection context.
# We connect async → get the connection → run sync Alembic ops on it.
# This is the standard workaround and is documented by Alembic.

import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# ── Import application models ─────────────────────────────────────────────────
# CRITICAL: These imports register the models into Base.metadata.
# Without these, autogenerate won't know about your tables.
from backend.database.base import Base
import backend.models  # noqa: F401 — imports all models via __init__.py

# ── Alembic Config Object ─────────────────────────────────────────────────────
# This is the alembic.ini config, parsed and available as a Python object.
config = context.config

# ── Logging Setup ─────────────────────────────────────────────────────────────
# Interpret the config file for Python logging.
# If alembic.ini has [loggers], [handlers], [formatters] sections, this
# sets up the logging system. This gives you INFO/WARN output during migrations.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Override the DB URL from environment ──────────────────────────────────────
# Rather than reading sqlalchemy.url from alembic.ini (which would hardcode
# credentials), we inject the URL from our app's settings (which reads .env).
# This keeps credentials in one place: the .env file.
import os
from backend.core.config import get_settings

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# ── Target Metadata ───────────────────────────────────────────────────────────
# This tells Alembic's autogenerate what to compare the DB against.
# Base.metadata contains the table definitions from all our SQLAlchemy models.
target_metadata = Base.metadata


# ── Offline Migration ─────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    In offline mode, Alembic generates SQL statements and prints/saves them
    WITHOUT connecting to a database. Useful for:
    - Generating SQL scripts for review before production deployment
    - Running in environments without DB access

    Command: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,          # Detect column type changes
        compare_server_default=True, # Detect server_default changes
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online Migration ──────────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    """
    Actual migration execution. Runs synchronously on the given connection.
    Called from run_migrations_online via run_sync().
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations on it.

    The trick: Alembic's run_migrations() is sync, but our engine is async.
    Solution: use connectable.run_sync(do_run_migrations) — this runs the
    sync Alembic code on a sync connection extracted from the async engine.
    This is the officially recommended pattern for async SQLAlchemy + Alembic.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections during migrations
        # NullPool creates a new connection per operation and closes it.
        # During migrations, we only need one connection — pooling adds no value
        # and can cause issues if the migration modifies tables still in the pool.
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the DB and applies changes.
    This wraps the async function using asyncio.run() since Alembic is sync.
    Command: alembic upgrade head
    """
    asyncio.run(run_async_migrations())


# ── Entry Point ───────────────────────────────────────────────────────────────
# Alembic calls env.py and checks: is this offline or online mode?
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
