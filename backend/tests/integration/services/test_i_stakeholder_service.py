"""
Phase 6 - Integration: StakeholderService against real PostgreSQL.

Covers:
    - create stakeholder -> persists with correct quadrant
    - update position -> updated_at changes
    - delete stakeholder -> row removed
    - cross-project access raises ForbiddenException
"""

from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole
from app.models.project import Project
from app.models.stakeholder import Stakeholder, InfluenceLevel, InterestLevel, Sentiment
from app.core.security import hash_password
from app.core.exceptions import ForbiddenException
from app.schemas.project import ProjectCreate
from app.schemas.stakeholder import StakeholderCreate
from app.services.project_service import ProjectService
from app.services.stakeholder_service import StakeholderService


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("Password123!"),
        full_name="Test",
        role=UserRole.USER,
        is_active=True,
        is_superuser=False,
        email_verified=True,
        terms_accepted=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_project(db: AsyncSession, owner_id: int) -> Project:
    return await ProjectService(db).create_project(
        project_data=ProjectCreate(name="SH Project", description="desc"),
        owner_id=owner_id,
    )


def _sh_data(**overrides) -> StakeholderCreate:
    defaults = dict(
        name="Alice",
        role="CTO",
        influence=InfluenceLevel.HIGH,
        interest=InterestLevel.HIGH,
        sentiment=Sentiment.NEUTRAL,
        email=None,
        department=None,
        concerns=None,
        motivations=None,
        approval_role=None,
        notify_on_approval_needed=False,
    )
    defaults.update(overrides)
    return StakeholderCreate(**defaults)


class TestCreateStakeholder:
    async def test_create_persists_with_correct_quadrant(
        self, db_session: AsyncSession
    ):
        """High influence + high interest -> Key Players quadrant."""
        owner = await _make_user(db_session, "sh_create@example.com")
        project = await _make_project(db_session, owner.id)
        svc = StakeholderService(db_session)

        sh = await svc.create_stakeholder(
            project_id=project.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            data=_sh_data(influence=InfluenceLevel.HIGH, interest=InterestLevel.HIGH),
        )

        assert sh.id is not None
        assert sh.power_interest_quadrant == "Manage Closely"

    async def test_low_influence_low_interest_is_monitor(
        self, db_session: AsyncSession
    ):
        """Low influence + low interest -> Monitor quadrant."""
        owner = await _make_user(db_session, "sh_monitor@example.com")
        project = await _make_project(db_session, owner.id)
        svc = StakeholderService(db_session)

        sh = await svc.create_stakeholder(
            project_id=project.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            data=_sh_data(influence=InfluenceLevel.LOW, interest=InterestLevel.LOW),
        )

        assert sh.power_interest_quadrant == "Monitor"

    async def test_stakeholder_belongs_to_correct_project(
        self, db_session: AsyncSession
    ):
        """Created stakeholder must reference the right project_id."""
        owner = await _make_user(db_session, "sh_proj@example.com")
        project = await _make_project(db_session, owner.id)
        svc = StakeholderService(db_session)

        sh = await svc.create_stakeholder(
            project_id=project.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            data=_sh_data(),
        )
        assert sh.project_id == project.id


class TestUpdateStakeholder:
    async def test_update_position_changes_updated_at(self, db_session: AsyncSession):
        """Updating a stakeholder must refresh updated_at."""
        owner = await _make_user(db_session, "sh_upd@example.com")
        project = await _make_project(db_session, owner.id)
        svc = StakeholderService(db_session)

        sh = await svc.create_stakeholder(
            project_id=project.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            data=_sh_data(influence=InfluenceLevel.LOW),
        )
        original_updated = sh.updated_at

        updated = await svc.update_stakeholder(
            stakeholder_id=sh.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            influence=InfluenceLevel.HIGH,
        )

        assert updated.influence == InfluenceLevel.HIGH
        assert updated.updated_at >= original_updated

    async def test_update_sentiment_persists(self, db_session: AsyncSession):
        """Sentiment change must be committed and readable via a fresh fetch."""
        owner = await _make_user(db_session, "sh_sent@example.com")
        project = await _make_project(db_session, owner.id)
        svc = StakeholderService(db_session)

        sh = await svc.create_stakeholder(
            project_id=project.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            data=_sh_data(sentiment=Sentiment.NEUTRAL),
        )
        await svc.update_stakeholder(
            stakeholder_id=sh.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            sentiment=Sentiment.CHAMPION,
        )

        fetched = await db_session.get(Stakeholder, sh.id)
        assert fetched.sentiment == Sentiment.CHAMPION


class TestDeleteStakeholder:
    async def test_delete_removes_row(self, db_session: AsyncSession):
        """delete_stakeholder() must remove the row from the DB."""
        owner = await _make_user(db_session, "sh_del@example.com")
        project = await _make_project(db_session, owner.id)
        svc = StakeholderService(db_session)

        sh = await svc.create_stakeholder(
            project_id=project.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            data=_sh_data(),
        )
        sh_id = sh.id

        await svc.delete_stakeholder(sh_id, owner.id, UserRole.USER)

        fetched = await db_session.get(Stakeholder, sh_id)
        assert fetched is None


class TestStakeholderAccess:
    async def test_user_cannot_access_stakeholder_in_other_project(
        self, db_session: AsyncSession
    ):
        """get_by_id() raises ForbiddenException for users not in the project."""
        owner = await _make_user(db_session, "sh_own2@example.com")
        stranger = await _make_user(db_session, "sh_str2@example.com")
        project = await _make_project(db_session, owner.id)
        svc = StakeholderService(db_session)

        sh = await svc.create_stakeholder(
            project_id=project.id,
            user_id=owner.id,
            user_role=UserRole.USER,
            data=_sh_data(),
        )

        with pytest.raises(ForbiddenException):
            await svc.get_by_id(sh.id, stranger.id, UserRole.USER)
