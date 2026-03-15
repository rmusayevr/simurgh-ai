"""
Unit tests for app/services/project_service.py

Covers:
    ProjectRole model helpers (pure Python):
        - can_edit: OWNER, ADMIN, EDITOR pass; VIEWER fails
        - can_manage: OWNER, ADMIN pass; EDITOR, VIEWER fail
        - can_delete: only OWNER
        - privilege_level ordering

    ProjectService.assert_can_edit:
        - System ADMIN always passes
        - Project owner always passes (no link row needed)
        - VIEWER role raises ForbiddenException
        - Missing link raises ForbiddenException

    ProjectService.assert_can_manage:
        - System ADMIN always passes
        - Project owner always passes
        - EDITOR role raises ForbiddenException

    ProjectService.get_by_id_or_404:
        - Raises NotFoundException when project not found

    ProjectService.archive_project:
        - Already archived raises BadRequestException
        - Active project gets archived (is_archived=True, archived_at set)

    ProjectService.unarchive_project:
        - Not archived raises BadRequestException
        - Archived project gets restored

    ProjectService.delete_project:
        - Non-owner non-admin raises ForbiddenException
        - Owner can delete
        - Admin can delete any project

    ProjectService.add_member:
        - Duplicate membership raises ConflictException
        - Valid add increments member_count

    ProjectService.remove_member:
        - User not a member raises NotFoundException
        - Owner cannot be removed (raises BadRequestException)
        - Valid removal decrements member_count

    ProjectService.update_member_role:
        - User not a member raises NotFoundException
        - Owner role change raises BadRequestException
        - Valid update persists new role

All DB calls mocked via AsyncMock.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.project import Project
from app.models.links import ProjectRole
from app.models.user import UserRole
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    ConflictException,
)
from tests.fixtures.projects import build_project, build_project_member_link


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(db_mock):
    from app.services.project_service import ProjectService

    return ProjectService(session=db_mock)


def _make_db_for_project(project: Project | None):
    db = AsyncMock()
    db.get = AsyncMock(return_value=project)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


def _make_exec_result(items):
    result = MagicMock()
    result.first.return_value = items[0] if items else None
    result.all.return_value = items
    return result


# ══════════════════════════════════════════════════════════════════
# ProjectRole helpers — pure Python
# ══════════════════════════════════════════════════════════════════


class TestProjectRoleHelpers:
    def test_owner_can_edit(self):
        assert ProjectRole.OWNER.can_edit is True

    def test_admin_can_edit(self):
        assert ProjectRole.ADMIN.can_edit is True

    def test_editor_can_edit(self):
        assert ProjectRole.EDITOR.can_edit is True

    def test_viewer_cannot_edit(self):
        assert ProjectRole.VIEWER.can_edit is False

    def test_owner_can_manage(self):
        assert ProjectRole.OWNER.can_manage is True

    def test_admin_can_manage(self):
        assert ProjectRole.ADMIN.can_manage is True

    def test_editor_cannot_manage(self):
        assert ProjectRole.EDITOR.can_manage is False

    def test_viewer_cannot_manage(self):
        assert ProjectRole.VIEWER.can_manage is False

    def test_only_owner_can_delete(self):
        assert ProjectRole.OWNER.can_delete is True
        assert ProjectRole.ADMIN.can_delete is False
        assert ProjectRole.EDITOR.can_delete is False
        assert ProjectRole.VIEWER.can_delete is False

    def test_privilege_levels_ordered_correctly(self):
        assert ProjectRole.VIEWER.privilege_level < ProjectRole.EDITOR.privilege_level
        assert ProjectRole.EDITOR.privilege_level < ProjectRole.ADMIN.privilege_level
        assert ProjectRole.ADMIN.privilege_level < ProjectRole.OWNER.privilege_level


# ══════════════════════════════════════════════════════════════════
# ProjectService.assert_can_edit
# ══════════════════════════════════════════════════════════════════


class TestAssertCanEdit:
    async def test_system_admin_always_passes(self):
        db = _make_db_for_project(build_project(id=1, owner_id=99))
        svc = _make_service(db)
        # Should not raise
        await svc.assert_can_edit(project_id=1, user_id=5, user_role=UserRole.ADMIN)

    async def test_project_owner_passes_without_link_row(self):
        project = build_project(id=1, owner_id=7)
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([]))  # no link row
        svc = _make_service(db)
        # Owner should pass even with no ProjectStakeholderLink
        await svc.assert_can_edit(project_id=1, user_id=7, user_role=UserRole.USER)

    async def test_editor_role_passes(self):
        project = build_project(id=1, owner_id=99)
        link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([link]))
        svc = _make_service(db)

        await svc.assert_can_edit(project_id=1, user_id=5, user_role=UserRole.USER)

    async def test_viewer_role_raises_forbidden(self):
        project = build_project(id=1, owner_id=99)
        link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.VIEWER
        )
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([link]))
        svc = _make_service(db)

        with pytest.raises(ForbiddenException):
            await svc.assert_can_edit(project_id=1, user_id=5, user_role=UserRole.USER)

    async def test_no_link_row_raises_forbidden(self):
        project = build_project(id=1, owner_id=99)
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        svc = _make_service(db)

        with pytest.raises(ForbiddenException):
            await svc.assert_can_edit(project_id=1, user_id=5, user_role=UserRole.USER)


# ══════════════════════════════════════════════════════════════════
# ProjectService.assert_can_manage
# ══════════════════════════════════════════════════════════════════


class TestAssertCanManage:
    async def test_system_admin_always_passes(self):
        db = _make_db_for_project(build_project(id=1))
        svc = _make_service(db)
        await svc.assert_can_manage(project_id=1, user_id=5, user_role=UserRole.ADMIN)

    async def test_project_owner_passes(self):
        project = build_project(id=1, owner_id=7)
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        svc = _make_service(db)
        await svc.assert_can_manage(project_id=1, user_id=7, user_role=UserRole.USER)

    async def test_editor_cannot_manage(self):
        project = build_project(id=1, owner_id=99)
        link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([link]))
        svc = _make_service(db)

        with pytest.raises(ForbiddenException):
            await svc.assert_can_manage(
                project_id=1, user_id=5, user_role=UserRole.USER
            )

    async def test_admin_project_role_can_manage(self):
        project = build_project(id=1, owner_id=99)
        link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.ADMIN
        )
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([link]))
        svc = _make_service(db)
        await svc.assert_can_manage(project_id=1, user_id=5, user_role=UserRole.USER)


# ══════════════════════════════════════════════════════════════════
# ProjectService.get_by_id_or_404
# ══════════════════════════════════════════════════════════════════


class TestGetByIdOr404:
    async def test_not_found_raises_not_found_exception(self):
        db = _make_db_for_project(None)
        svc = _make_service(db)

        with pytest.raises(NotFoundException, match="Project not found"):
            await svc.get_by_id_or_404(999)

    async def test_found_returns_project(self):
        project = build_project(id=5)
        db = _make_db_for_project(project)
        svc = _make_service(db)

        result = await svc.get_by_id_or_404(5)
        assert result is project


# ══════════════════════════════════════════════════════════════════
# ProjectService.archive_project / unarchive_project
# ══════════════════════════════════════════════════════════════════


class TestArchiveProject:
    async def test_archive_already_archived_raises_bad_request(self):
        project = build_project(id=1)
        project.archive()  # already archived
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()  # skip permission check

        with pytest.raises(BadRequestException, match="already archived"):
            await svc.archive_project(1, user_id=1, user_role=UserRole.USER)

    async def test_active_project_gets_archived(self):
        project = build_project(id=1, is_archived=False)
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.archive_project(1, user_id=1, user_role=UserRole.USER)

        assert project.is_archived is True
        assert project.archived_at is not None

    async def test_unarchive_not_archived_raises_bad_request(self):
        project = build_project(id=1, is_archived=False)
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        with pytest.raises(BadRequestException, match="not archived"):
            await svc.unarchive_project(1, user_id=1, user_role=UserRole.USER)

    async def test_archived_project_gets_restored(self):
        project = build_project(id=1)
        project.archive()
        db = _make_db_for_project(project)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.unarchive_project(1, user_id=1, user_role=UserRole.USER)

        assert project.is_archived is False
        assert project.archived_at is None


# ══════════════════════════════════════════════════════════════════
# ProjectService.delete_project
# ══════════════════════════════════════════════════════════════════


class TestDeleteProject:
    async def test_non_owner_non_admin_raises_forbidden(self):
        project = build_project(id=1, owner_id=99)
        db = _make_db_for_project(project)
        svc = _make_service(db)

        with pytest.raises(ForbiddenException):
            await svc.delete_project(project_id=1, user_id=5, user_role=UserRole.USER)

    async def test_owner_can_delete(self):
        project = build_project(id=1, owner_id=5)
        db = _make_db_for_project(project)
        svc = _make_service(db)

        await svc.delete_project(project_id=1, user_id=5, user_role=UserRole.USER)
        db.delete.assert_called_once_with(project)

    async def test_system_admin_can_delete_any_project(self):
        project = build_project(id=1, owner_id=99)
        db = _make_db_for_project(project)
        svc = _make_service(db)

        await svc.delete_project(project_id=1, user_id=1, user_role=UserRole.ADMIN)
        db.delete.assert_called_once_with(project)

    async def test_delete_calls_commit(self):
        project = build_project(id=1, owner_id=5)
        db = _make_db_for_project(project)
        svc = _make_service(db)

        await svc.delete_project(project_id=1, user_id=5, user_role=UserRole.USER)
        db.commit.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# ProjectService.add_member
# ══════════════════════════════════════════════════════════════════


class TestAddMember:
    def _setup_db(self, project: Project, existing_link=None):
        db = AsyncMock()
        db.get = AsyncMock(return_value=project)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        # get_user_role query result
        db.exec = AsyncMock(
            return_value=_make_exec_result([existing_link] if existing_link else [])
        )
        return db

    async def test_duplicate_member_raises_conflict(self):
        project = build_project(id=1, owner_id=99)
        existing = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = self._setup_db(project, existing_link=existing)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        with pytest.raises(ConflictException, match="already a member"):
            await svc.add_member(
                project_id=1,
                target_user_id=5,
                role=ProjectRole.EDITOR,
                requester_id=99,
                requester_role=UserRole.USER,
            )

    async def test_valid_add_creates_link_row(self):
        project = build_project(id=1, owner_id=99, member_count=1)
        db = self._setup_db(project, existing_link=None)
        # After adding, refresh should return the link
        db.refresh = AsyncMock()
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.add_member(
            project_id=1,
            target_user_id=5,
            role=ProjectRole.EDITOR,
            requester_id=99,
            requester_role=UserRole.USER,
        )

        db.add.assert_called()

    async def test_valid_add_increments_member_count(self):
        project = build_project(id=1, owner_id=99, member_count=2)
        db = self._setup_db(project, existing_link=None)
        db.refresh = AsyncMock()
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.add_member(
            project_id=1,
            target_user_id=5,
            role=ProjectRole.VIEWER,
            requester_id=99,
            requester_role=UserRole.USER,
        )

        assert project.member_count == 3


# ══════════════════════════════════════════════════════════════════
# ProjectService.remove_member
# ══════════════════════════════════════════════════════════════════


class TestRemoveMember:
    def _setup_db(self, project: Project, link=None):
        db = AsyncMock()
        db.get = AsyncMock(return_value=project)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.delete = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([link] if link else []))
        return db

    async def test_not_a_member_raises_not_found(self):
        project = build_project(id=1, owner_id=99)
        db = self._setup_db(project, link=None)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        with pytest.raises(NotFoundException, match="not a member"):
            await svc.remove_member(
                project_id=1,
                target_user_id=5,
                requester_id=99,
                requester_role=UserRole.USER,
            )

    async def test_owner_cannot_be_removed(self):
        project = build_project(id=1, owner_id=99)
        owner_link = build_project_member_link(
            project_id=1, user_id=99, role=ProjectRole.OWNER
        )
        db = self._setup_db(project, link=owner_link)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        with pytest.raises(BadRequestException, match="owner cannot be removed"):
            await svc.remove_member(
                project_id=1,
                target_user_id=99,
                requester_id=99,
                requester_role=UserRole.USER,
            )

    async def test_valid_removal_deletes_link(self):
        project = build_project(id=1, owner_id=99, member_count=3)
        editor_link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = self._setup_db(project, link=editor_link)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.remove_member(
            project_id=1,
            target_user_id=5,
            requester_id=99,
            requester_role=UserRole.USER,
        )

        db.delete.assert_called_once_with(editor_link)

    async def test_valid_removal_decrements_member_count(self):
        project = build_project(id=1, owner_id=99, member_count=3)
        editor_link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = self._setup_db(project, link=editor_link)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.remove_member(
            project_id=1,
            target_user_id=5,
            requester_id=99,
            requester_role=UserRole.USER,
        )

        assert project.member_count == 2

    async def test_member_count_does_not_go_below_zero(self):
        project = build_project(id=1, owner_id=99, member_count=0)
        editor_link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = self._setup_db(project, link=editor_link)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.remove_member(
            project_id=1,
            target_user_id=5,
            requester_id=99,
            requester_role=UserRole.USER,
        )

        assert project.member_count == 0


# ══════════════════════════════════════════════════════════════════
# ProjectService.update_member_role
# ══════════════════════════════════════════════════════════════════


class TestUpdateMemberRole:
    def _setup_db(self, project: Project, link=None):
        db = AsyncMock()
        db.get = AsyncMock(return_value=project)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([link] if link else []))
        return db

    async def test_not_a_member_raises_not_found(self):
        project = build_project(id=1, owner_id=99)
        db = self._setup_db(project, link=None)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        with pytest.raises(NotFoundException):
            await svc.update_member_role(
                project_id=1,
                target_user_id=5,
                new_role=ProjectRole.EDITOR,
                requester_id=99,
                requester_role=UserRole.USER,
            )

    async def test_changing_owner_role_raises_bad_request(self):
        project = build_project(id=1, owner_id=99)
        owner_link = build_project_member_link(
            project_id=1, user_id=99, role=ProjectRole.OWNER
        )
        db = self._setup_db(project, link=owner_link)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        with pytest.raises(BadRequestException, match="owner"):
            await svc.update_member_role(
                project_id=1,
                target_user_id=99,
                new_role=ProjectRole.EDITOR,
                requester_id=99,
                requester_role=UserRole.USER,
            )

    async def test_valid_role_update_persists(self):
        project = build_project(id=1, owner_id=99)
        editor_link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = self._setup_db(project, link=editor_link)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.update_member_role(
            project_id=1,
            target_user_id=5,
            new_role=ProjectRole.VIEWER,
            requester_id=99,
            requester_role=UserRole.USER,
        )

        assert editor_link.role == ProjectRole.VIEWER

    async def test_valid_role_update_calls_commit(self):
        project = build_project(id=1, owner_id=99)
        editor_link = build_project_member_link(
            project_id=1, user_id=5, role=ProjectRole.EDITOR
        )
        db = self._setup_db(project, link=editor_link)
        svc = _make_service(db)
        svc.assert_can_manage = AsyncMock()

        await svc.update_member_role(
            project_id=1,
            target_user_id=5,
            new_role=ProjectRole.ADMIN,
            requester_id=99,
            requester_role=UserRole.USER,
        )

        db.commit.assert_called_once()
