"""Phase 7 — API: Project endpoints."""

from unittest.mock import AsyncMock, patch
from datetime import datetime
from app.models.project import ProjectVisibility

BASE = "/api/v1/projects"


def _proj(id=1, owner_id=1):
    from unittest.mock import MagicMock

    p = MagicMock()
    p.id = id
    p.owner_id = owner_id
    p.name = "Test Project"
    p.description = "desc"
    p.visibility = ProjectVisibility.PRIVATE  # ← required enum
    p.is_archived = False
    p.owner = None
    p.tags = None
    p.tech_stack = None
    p.member_count = 1
    p.document_count = 0  # ← required int
    p.proposal_count = 0  # ← required int
    p.stakeholder_links = []
    p.historical_documents = []
    p.created_at = datetime(2024, 1, 1)
    p.updated_at = datetime(2024, 1, 1)
    p.last_activity_at = datetime(2024, 1, 1)  # ← required datetime
    p.archived_at = None
    return p


class TestCreateProject:
    async def test_create_returns_201(self, user_client):
        from app.services.project_service import ProjectService

        with patch.object(
            ProjectService, "create_project", new=AsyncMock(return_value=_proj())
        ):
            resp = await user_client.post(
                BASE + "/", json={"name": "P", "description": "d"}
            )
        assert resp.status_code == 201

    async def test_create_requires_auth(self, client):
        assert (await client.post(BASE + "/", json={"name": "P"})).status_code == 401

    async def test_create_missing_name_returns_422(self, user_client):
        assert (
            await user_client.post(BASE + "/", json={"description": "d"})
        ).status_code == 422


class TestListProjects:
    async def test_list_returns_200(self, user_client):
        from app.services.project_service import ProjectService

        with patch.object(
            ProjectService, "get_user_projects", new=AsyncMock(return_value=[])
        ):
            resp = await user_client.get(BASE + "/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_requires_auth(self, client):
        assert (await client.get(BASE + "/")).status_code == 401


class TestGetProject:
    async def test_get_owner_returns_200(self, user_client):
        from app.services.project_service import ProjectService

        with patch.object(
            ProjectService, "get_project_by_id", new=AsyncMock(return_value=_proj(id=1))
        ):
            resp = await user_client.get(f"{BASE}/1")
        assert resp.status_code == 200

    async def test_get_non_member_returns_403(self, user_client):
        from app.services.project_service import ProjectService
        from app.core.exceptions import ForbiddenException

        with patch.object(
            ProjectService,
            "get_project_by_id",
            new=AsyncMock(side_effect=ForbiddenException("no access")),
        ):
            resp = await user_client.get(f"{BASE}/99")
        assert resp.status_code == 403

    async def test_get_nonexistent_returns_404(self, user_client):
        from app.services.project_service import ProjectService
        from app.core.exceptions import NotFoundException

        with patch.object(
            ProjectService,
            "get_project_by_id",
            new=AsyncMock(side_effect=NotFoundException("nf")),
        ):
            resp = await user_client.get(f"{BASE}/9999")
        assert resp.status_code == 404

    async def test_get_requires_auth(self, client):
        assert (await client.get(f"{BASE}/1")).status_code == 401


class TestDeleteProject:
    async def test_delete_owner_returns_204(self, user_client):
        from app.services.project_service import ProjectService

        with patch.object(
            ProjectService, "delete_project", new=AsyncMock(return_value=None)
        ):
            resp = await user_client.delete(f"{BASE}/1")
        assert resp.status_code == 204

    async def test_delete_non_owner_returns_403(self, user_client):
        from app.services.project_service import ProjectService
        from app.core.exceptions import ForbiddenException

        with patch.object(
            ProjectService,
            "delete_project",
            new=AsyncMock(side_effect=ForbiddenException("not owner")),
        ):
            resp = await user_client.delete(f"{BASE}/2")
        assert resp.status_code == 403

    async def test_delete_requires_auth(self, client):
        assert (await client.delete(f"{BASE}/1")).status_code == 401
