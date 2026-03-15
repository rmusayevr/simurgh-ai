"""
Database helpers for integration tests.

Provides:
    - truncate_tables:  Wipe all app tables between integration tests
    - seed_minimal:     Insert the bare-minimum rows needed for most tests
    - table_row_count:  Assert exact row counts in CI
    - assert_db_clean:  Fail fast if test pollution is detected

These helpers are only used by integration/conftest.py and integration tests.
Unit tests and API tests use mock sessions instead.
"""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text


# ── Tables ordered to respect FK constraints (children before parents) ─────────

# Delete order: dependents first, then parents
_DELETE_ORDER = [
    "token_usage_records",
    "document_chunks",
    "debate_sessions",
    "proposal_variations",
    "proposals",
    "historical_documents",
    "persona_coding_records",
    "exit_survey_responses",
    "questionnaire_responses",
    "participants",
    "stakeholders",
    "project_stakeholder_links",
    "refresh_tokens",
    "projects",
    "users",
    "prompt_templates",
    "system_settings",
]


async def truncate_tables(
    session: AsyncSession, tables: list[str] | None = None
) -> None:
    """
    DELETE all rows from specified tables (or all app tables by default).

    Uses DELETE instead of TRUNCATE to avoid requiring TRUNCATE privilege
    and to play nicely with transaction-level rollback in tests.

    Args:
        session: Active AsyncSession (typically from integration conftest)
        tables:  Optional subset of table names. Defaults to full _DELETE_ORDER.

    Usage:
        async def test_something(db_session):
            await truncate_tables(db_session)
            # DB is now empty
    """
    target_tables = tables or _DELETE_ORDER
    for table in target_tables:
        await session.exec(text(f"DELETE FROM {table}"))
    await session.commit()


async def seed_minimal(session: AsyncSession) -> dict:
    """
    Insert the minimum set of rows required for most integration tests.

    Creates:
        - 1 superuser  (id will be assigned by DB)
        - 1 normal user
        - 1 project owned by the normal user

    Returns:
        dict with keys: "superuser", "user", "project"

    Usage:
        async def test_project_crud(db_session):
            seed = await seed_minimal(db_session)
            project = seed["project"]
    """
    from app.models.user import User, UserRole
    from app.models.project import Project
    from app.core.security import hash_password

    superuser = User(
        email="superuser@test.example",
        hashed_password=hash_password("SuperPass123!"),
        full_name="Super User",
        role=UserRole.ADMIN,
        is_active=True,
        is_superuser=True,
        email_verified=True,
        terms_accepted=True,
    )
    session.add(superuser)

    user = User(
        email="user@test.example",
        hashed_password=hash_password("UserPass123!"),
        full_name="Test User",
        role=UserRole.USER,
        is_active=True,
        is_superuser=False,
        email_verified=True,
        terms_accepted=True,
    )
    session.add(user)

    await session.flush()  # assigns IDs without committing

    project = Project(
        name="Test Project",
        description="Seeded project for integration tests",
        owner_id=user.id,
    )
    session.add(project)
    await session.commit()

    await session.refresh(superuser)
    await session.refresh(user)
    await session.refresh(project)

    return {"superuser": superuser, "user": user, "project": project}


async def table_row_count(session: AsyncSession, table: str) -> int:
    """
    Return the number of rows in a table.

    Usage:
        count = await table_row_count(session, "users")
        assert count == 2
    """
    result = await session.exec(text(f"SELECT COUNT(*) FROM {table}"))
    return result.scalar()


async def assert_db_clean(
    session: AsyncSession, tables: list[str] | None = None
) -> None:
    """
    Assert that all (or specified) tables are empty.

    Useful at the start of a test to detect pollution from a previous run.

    Raises:
        AssertionError: If any table has rows

    Usage:
        async def test_something(db_session):
            await assert_db_clean(db_session)
    """
    target_tables = tables or _DELETE_ORDER
    for table in target_tables:
        count = await table_row_count(session, table)
        assert count == 0, (
            f"Table '{table}' has {count} row(s) — test pollution detected. "
            "Ensure tests run in isolated transactions or call truncate_tables() first."
        )
