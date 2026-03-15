"""
Phase 6 - Integration: ProjectService against real PostgreSQL.

Covers:
    - create project -> owner relationship is correct
    - add member -> ProjectStakeholderLink row created
    - remove member -> link row deleted
    - non-member access raises NotFoundException
    - delete project removes the row
    - archive / unarchive toggle
"""

from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.user import User, UserRole
from app.models.project import Project
from app.models.links import ProjectStakeholderLink, ProjectRole
from app.core.security import hash_password
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    BadRequestException,
    ConflictException,
)
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService


async def _make_user(
    db: AsyncSession, email: str, role: UserRole = UserRole.USER
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("Password123!"),
        full_name="Test User",
        role=role,
        is_active=True,
        is_superuser=False,
        email_verified=True,
        terms_accepted=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_project(
    db: AsyncSession, owner_id: int, name: str = "Test Project"
) -> Project:
    svc = ProjectService(db)
    return await svc.create_project(
        project_data=ProjectCreate(name=name, description="Integration test project"),
        owner_id=owner_id,
    )


class TestCreateProject:
    async def test_create_project_persists_to_db(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "projowner@example.com")
        svc = ProjectService(db_session)

        project = await svc.create_project(
            project_data=ProjectCreate(name="My Project", description="Desc"),
            owner_id=owner.id,
        )

        assert project.id is not None
        fetched = await db_session.get(Project, project.id)
        assert fetched is not None
        assert fetched.name == "My Project"

    async def test_create_project_sets_owner(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "owner2@example.com")
        project = await _make_project(db_session, owner.id)
        assert project.owner_id == owner.id

    async def test_create_project_creates_owner_link(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "ownerlink@example.com")
        project = await _make_project(db_session, owner.id)

        result = await db_session.exec(
            select(ProjectStakeholderLink).where(
                ProjectStakeholderLink.project_id == project.id,
                ProjectStakeholderLink.user_id == owner.id,
            )
        )
        link = result.first()
        assert link is not None
        assert link.role == ProjectRole.OWNER


class TestMemberManagement:
    async def test_add_member_creates_link_row(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "addmem_owner@example.com")
        member = await _make_user(db_session, "addmem_member@example.com")
        project = await _make_project(db_session, owner.id)

        svc = ProjectService(db_session)
        link = await svc.add_member(
            project_id=project.id,
            target_user_id=member.id,
            role=ProjectRole.EDITOR,
            requester_id=owner.id,
            requester_role=UserRole.USER,
        )

        assert link.user_id == member.id
        assert link.project_id == project.id
        assert link.role == ProjectRole.EDITOR

    async def test_add_member_increments_member_count(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "count_owner@example.com")
        member = await _make_user(db_session, "count_member@example.com")
        project = await _make_project(db_session, owner.id)
        initial_count = project.member_count

        svc = ProjectService(db_session)
        await svc.add_member(
            project_id=project.id,
            target_user_id=member.id,
            role=ProjectRole.VIEWER,
            requester_id=owner.id,
            requester_role=UserRole.USER,
        )

        await db_session.refresh(project)
        assert project.member_count == initial_count + 1

    async def test_add_duplicate_member_raises_conflict(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "dup_owner@example.com")
        member = await _make_user(db_session, "dup_member@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        await svc.add_member(
            project_id=project.id,
            target_user_id=member.id,
            role=ProjectRole.EDITOR,
            requester_id=owner.id,
            requester_role=UserRole.USER,
        )

        with pytest.raises(ConflictException):
            await svc.add_member(
                project_id=project.id,
                target_user_id=member.id,
                role=ProjectRole.VIEWER,
                requester_id=owner.id,
                requester_role=UserRole.USER,
            )

    async def test_remove_member_deletes_link_row(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "remmem_owner@example.com")
        member = await _make_user(db_session, "remmem_member@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        await svc.add_member(
            project_id=project.id,
            target_user_id=member.id,
            role=ProjectRole.EDITOR,
            requester_id=owner.id,
            requester_role=UserRole.USER,
        )
        await svc.remove_member(
            project_id=project.id,
            target_user_id=member.id,
            requester_id=owner.id,
            requester_role=UserRole.USER,
        )

        result = await db_session.exec(
            select(ProjectStakeholderLink).where(
                ProjectStakeholderLink.project_id == project.id,
                ProjectStakeholderLink.user_id == member.id,
            )
        )
        assert result.first() is None

    async def test_remove_owner_raises_bad_request(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "remown_owner@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        with pytest.raises(BadRequestException):
            await svc.remove_member(
                project_id=project.id,
                target_user_id=owner.id,
                requester_id=owner.id,
                requester_role=UserRole.USER,
            )


class TestProjectAccess:
    async def test_non_member_cannot_access_project(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "accown@example.com")
        stranger = await _make_user(db_session, "accstr@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        with pytest.raises(NotFoundException):
            await svc.get_project_by_id(
                project_id=project.id,
                user_id=stranger.id,
                user_role=UserRole.USER,
            )

    async def test_admin_can_access_any_project(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "admacc_owner@example.com")
        admin = await _make_user(
            db_session, "admacc_admin@example.com", role=UserRole.ADMIN
        )
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        result = await svc.get_project_by_id(
            project_id=project.id,
            user_id=admin.id,
            user_role=UserRole.ADMIN,
        )
        assert result.id == project.id


class TestArchiveProject:
    async def test_archive_sets_is_archived_true(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "arc_owner@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        archived = await svc.archive_project(project.id, owner.id, UserRole.USER)
        assert archived.is_archived is True

    async def test_archive_already_archived_raises_bad_request(
        self, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "arc2_owner@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        await svc.archive_project(project.id, owner.id, UserRole.USER)
        with pytest.raises(BadRequestException):
            await svc.archive_project(project.id, owner.id, UserRole.USER)

    async def test_unarchive_restores_project(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "unarc_owner@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        await svc.archive_project(project.id, owner.id, UserRole.USER)
        restored = await svc.unarchive_project(project.id, owner.id, UserRole.USER)
        assert restored.is_archived is False


class TestDeleteProject:
    async def test_delete_removes_project_row(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "del_owner@example.com")
        project = await _make_project(db_session, owner.id)
        project_id = project.id
        svc = ProjectService(db_session)

        await svc.delete_project(project_id, owner.id, UserRole.USER)

        fetched = await db_session.get(Project, project_id)
        assert fetched is None

    async def test_non_owner_cannot_delete_project(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "del2_owner@example.com")
        other = await _make_user(db_session, "del2_other@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProjectService(db_session)

        with pytest.raises(ForbiddenException):
            await svc.delete_project(project.id, other.id, UserRole.USER)
