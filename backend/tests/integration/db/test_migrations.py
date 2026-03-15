"""
Phase 5 — Integration: Database migration tests.

Verifies that the full Alembic migration chain is correct and idempotent:
    - upgrade head runs cleanly on a schema already at head (no-op)
    - downgrade base / upgrade head round-trip is idempotent
    - all expected tables exist after upgrade head
    - alembic_version table records the correct head revision
    - columns added by incremental migrations are present

Key constraints:
    - alembic/env.py reads DATABASE_URL from os.environ (ignores cfg sqlalchemy.url),
      so we patch os.environ before every command.upgrade/downgrade call.
    - command.upgrade/downgrade call asyncio.run() internally; they MUST be called
      from sync (def) tests, never from async def tests.
    - token_usage_records is present at HEAD in the squashed 0001 migration.
"""

from __future__ import annotations

import asyncio
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# ── Helpers ────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))


def _get_async_test_url() -> str:
    raw = os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db"
        ),
    )
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgresql://") and "+asyncpg" not in raw:
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


def _alembic_cfg() -> Config:
    """
    Build Alembic Config and ensure os.environ["DATABASE_URL"] is set to the
    test URL. alembic/env.py reads DATABASE_URL from os.environ directly and
    ignores the cfg sqlalchemy.url option entirely.
    """
    os.environ["DATABASE_URL"] = _get_async_test_url()
    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    return cfg


def _make_engine():
    return create_async_engine(_get_async_test_url(), poolclass=NullPool, future=True)


def _inspect_tables() -> set[str]:
    """Synchronously inspect table names via a fresh asyncio run."""

    async def _fetch():
        engine = _make_engine()
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(
                    lambda sync_conn: set(inspect(sync_conn).get_table_names())
                )
        finally:
            await engine.dispose()

    return asyncio.run(_fetch())


def _fetch_alembic_version() -> str | None:
    """Synchronously fetch the current alembic version string."""

    async def _fetch():
        engine = _make_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                row = result.fetchone()
                return row[0] if row else None
        finally:
            await engine.dispose()

    return asyncio.run(_fetch())


def _inspect_columns(table: str) -> list[str]:
    """Synchronously fetch column names for a table."""

    async def _fetch():
        engine = _make_engine()
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(
                    lambda sync_conn: [
                        c["name"] for c in inspect(sync_conn).get_columns(table)
                    ]
                )
        finally:
            await engine.dispose()

    return asyncio.run(_fetch())


# ── Expected schema at HEAD ────────────────────────────────────────────────────
#
# token_usage_records: present at HEAD in the squashed 0001 migration.

_EXPECTED_TABLES = {
    "users",
    "projects",
    "project_stakeholder_links",
    "stakeholders",
    "proposals",
    "proposal_variations",
    "debate_sessions",
    "historical_documents",
    "document_chunks",
    "refresh_tokens",
    "system_settings",
    "prompt_templates",
    "participants",
    "questionnaire_responses",
    "persona_codings",
    "exit_surveys",
    "task_documents",
    "token_usage_records",
}

_HEAD_REVISION = "0003"


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestMigrationsUpgrade:
    def test_upgrade_head_runs_without_error(self):
        """
        `alembic upgrade head` on an already-migrated DB must be a silent no-op.
        This is the canonical idempotency check — it must never raise.
        """
        command.upgrade(_alembic_cfg(), "head")

    def test_expected_tables_exist_after_upgrade(self):
        """All application tables must be present after upgrade head."""
        existing = _inspect_tables()
        missing = _EXPECTED_TABLES - existing
        assert not missing, (
            f"Tables missing after `alembic upgrade head`: {sorted(missing)}"
        )

    def test_alembic_version_is_at_head(self):
        """alembic_version must record the correct head revision."""
        version = _fetch_alembic_version()
        assert version is not None, "alembic_version is empty — migrations not run?"
        assert version == _HEAD_REVISION, (
            f"Expected head revision {_HEAD_REVISION!r}, got {version!r}"
        )


class TestMigrationsRoundTrip:
    def test_downgrade_one_then_upgrade_is_idempotent(self):
        """
        downgrade -1 then upgrade head must complete without error.

        Catches migrations that leave orphaned objects (triggers, sequences,
        types) that block a subsequent re-upgrade.
        """
        cfg = _alembic_cfg()
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")

    def test_schema_is_complete_after_round_trip(self):
        """After a downgrade/upgrade cycle all expected tables must still exist."""
        cfg = _alembic_cfg()
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")

        existing = _inspect_tables()
        missing = _EXPECTED_TABLES - existing
        assert not missing, f"Tables missing after round-trip: {sorted(missing)}"


class TestMigrationsColumns:
    def test_questionnaire_responses_has_condition_order(self):
        """condition_order is present in the squashed 0001 migration."""
        columns = _inspect_columns("questionnaire_responses")
        assert "condition_order" in columns, (
            "condition_order missing from questionnaire_responses"
        )

    def test_debate_sessions_has_consensus_confidence(self):
        """consensus_confidence is present in the squashed 0001 migration."""
        columns = _inspect_columns("debate_sessions")
        assert "consensus_confidence" in columns, (
            "consensus_confidence missing from debate_sessions"
        )

    def test_exit_surveys_has_preferred_system_actual(self):
        """preferred_system_actual is present in the squashed 0001 migration."""
        columns = _inspect_columns("exit_surveys")
        assert "preferred_system_actual" in columns, (
            "preferred_system_actual missing from exit_surveys"
        )
