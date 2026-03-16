"""Phase 7 — API: Proposal endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.models.proposal import ApprovalStatus, ProposalStatus

BASE = "/api/v1/proposals"
PID = 1
PROP_ID = 10


def _prop(id=PROP_ID, project_id=PID):
    p = MagicMock()
    p.id = id
    p.project_id = project_id
    p.task_description = "Migrate"
    p.structured_prd = None
    p.status = ProposalStatus.DRAFT  # ← real enum, not string
    p.approval_status = ApprovalStatus.PENDING_APPROVAL  # ← real enum, not string
    p.error_message = None
    p.selected_variation_id = None
    p.created_by_id = 1
    p.approved_by_id = None
    p.approved_at = None
    p.variations = []
    p.task_documents = []
    p.created_at = datetime(2024, 1, 1)
    p.updated_at = datetime(2024, 1, 1)
    # Export fields — must be None not MagicMock for ProposalRead validation
    p.jira_epic_key = None
    p.jira_epic_url = None
    p.jira_project_key = None
    p.jira_exported_at = None
    p.confluence_page_id = None
    p.confluence_page_url = None
    p.confluence_space_key = None
    p.confluence_exported_at = None
    return p


class TestCreateDraftProposal:
    async def test_create_draft_returns_201(self, user_client):
        from app.services.proposal_service import ProposalService

        with patch.object(
            ProposalService, "create_proposal", new=AsyncMock(return_value=_prop())
        ):
            resp = await user_client.post(
                f"{BASE}/draft",
                json={
                    "project_id": PID,
                    "task_description": "Migrate to microservices",
                },
            )
        assert resp.status_code == 201

    async def test_create_draft_requires_auth(self, client):
        assert (
            await client.post(
                f"{BASE}/draft", json={"project_id": PID, "task_description": "T"}
            )
        ).status_code == 401

    async def test_create_draft_missing_fields_returns_422(self, user_client):
        assert (await user_client.post(f"{BASE}/draft", json={})).status_code == 422


class TestGetProposal:
    async def test_get_returns_200(self, user_client):
        from app.services.proposal_service import ProposalService

        with patch.object(
            ProposalService, "get_by_id", new=AsyncMock(return_value=_prop())
        ):
            resp = await user_client.get(f"{BASE}/{PROP_ID}")
        assert resp.status_code == 200

    async def test_get_nonexistent_returns_404(self, user_client):
        from app.services.proposal_service import ProposalService
        from app.core.exceptions import NotFoundException

        with patch.object(
            ProposalService,
            "get_by_id",
            new=AsyncMock(side_effect=NotFoundException("nf")),
        ):
            resp = await user_client.get(f"{BASE}/9999")
        assert resp.status_code == 404

    async def test_get_requires_auth(self, client):
        assert (await client.get(f"{BASE}/{PROP_ID}")).status_code == 401


class TestListProjectProposals:
    async def test_list_returns_200(self, user_client):
        from app.services.proposal_service import ProposalService

        with patch.object(
            ProposalService,
            "get_proposals_by_project",
            new=AsyncMock(return_value=[_prop()]),
        ):
            resp = await user_client.get(f"{BASE}/project/{PID}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_requires_auth(self, client):
        assert (await client.get(f"{BASE}/project/{PID}")).status_code == 401


class TestDeleteProposal:
    async def test_delete_returns_204(self, user_client):
        from app.services.proposal_service import ProposalService

        with patch.object(
            ProposalService, "delete_proposal", new=AsyncMock(return_value=None)
        ):
            resp = await user_client.delete(f"{BASE}/{PROP_ID}")
        assert resp.status_code == 204

    async def test_delete_forbidden_returns_403(self, user_client):
        from app.services.proposal_service import ProposalService
        from app.core.exceptions import ForbiddenException

        with patch.object(
            ProposalService,
            "delete_proposal",
            new=AsyncMock(side_effect=ForbiddenException("no access")),
        ):
            resp = await user_client.delete(f"{BASE}/{PROP_ID}")
        assert resp.status_code == 403

    async def test_delete_requires_auth(self, client):
        assert (await client.delete(f"{BASE}/{PROP_ID}")).status_code == 401
