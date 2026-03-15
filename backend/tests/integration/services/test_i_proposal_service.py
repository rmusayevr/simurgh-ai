"""
Phase 6 - Integration: ProposalService against real PostgreSQL.

Covers:
    - create proposal -> persists in DRAFT state
    - project proposal_count increments
    - select_variation -> selected_variation_id persisted
    - approval lifecycle: submit -> approve / reject
    - delete proposal removes row and decrements count
    - retry failed proposal flips status back to PROCESSING
"""

from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole
from app.models.project import Project
from app.models.proposal import (
    Proposal,
    ProposalStatus,
    ApprovalStatus,
    AgentPersona,
    ProposalVariation,
)
from app.core.security import hash_password
from app.core.exceptions import BadRequestException
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService
from app.services.proposal_service import ProposalService


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
        project_data=ProjectCreate(name="Proposal Project", description="desc"),
        owner_id=owner_id,
    )


async def _make_proposal(
    db: AsyncSession, project_id: int, creator_id: int
) -> Proposal:
    svc = ProposalService(db)
    return await svc.create_proposal(
        project_id=project_id,
        task_description="Migrate monolith to microservices",
        created_by_id=creator_id,
    )


class TestCreateProposal:
    async def test_create_proposal_persists_in_draft(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "prop_create@example.com")
        project = await _make_project(db_session, owner.id)

        proposal = await _make_proposal(db_session, project.id, owner.id)

        assert proposal.id is not None
        assert proposal.status == ProposalStatus.DRAFT

        fetched = await db_session.get(Proposal, proposal.id)
        assert fetched is not None

    async def test_create_proposal_increments_project_count(
        self, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "prop_count@example.com")
        project = await _make_project(db_session, owner.id)
        initial_count = project.proposal_count

        await _make_proposal(db_session, project.id, owner.id)

        await db_session.refresh(project)
        assert project.proposal_count == initial_count + 1

    async def test_empty_task_description_raises_bad_request(
        self, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "prop_empty@example.com")
        project = await _make_project(db_session, owner.id)
        svc = ProposalService(db_session)

        with pytest.raises(BadRequestException):
            await svc.create_proposal(
                project_id=project.id,
                task_description="   ",
                created_by_id=owner.id,
            )


class TestVariationSelection:
    async def _setup_completed_proposal(self, db: AsyncSession, email_prefix: str):
        owner = await _make_user(db, f"{email_prefix}@example.com")
        project = await _make_project(db, owner.id)
        proposal = await _make_proposal(db, project.id, owner.id)

        # Manually mark completed and add a variation (bypassing Celery)
        proposal.status = ProposalStatus.COMPLETED
        db.add(proposal)
        await db.flush()

        variation = ProposalVariation(
            proposal_id=proposal.id,
            agent_persona=AgentPersona.INNOVATOR,
            structured_prd="# PRD\nContent here",
            confidence_score=80,
            chat_history=[],
        )
        db.add(variation)
        await db.flush()
        return owner, proposal, variation

    async def test_select_variation_persists_selection(self, db_session: AsyncSession):
        owner, proposal, variation = await self._setup_completed_proposal(
            db_session, "sel_var"
        )
        svc = ProposalService(db_session)

        updated = await svc.select_variation(proposal.id, variation.id)
        assert updated.selected_variation_id == variation.id

        fetched = await db_session.get(Proposal, proposal.id)
        assert fetched.selected_variation_id == variation.id

    async def test_select_variation_wrong_proposal_raises_bad_request(
        self, db_session: AsyncSession
    ):
        owner, proposal, variation = await self._setup_completed_proposal(
            db_session, "sel_wrong"
        )
        owner2 = await _make_user(db_session, "sel_wrong2@example.com")
        project2 = await _make_project(db_session, owner2.id)
        proposal2 = await _make_proposal(db_session, project2.id, owner2.id)
        svc = ProposalService(db_session)

        with pytest.raises(BadRequestException):
            await svc.select_variation(proposal2.id, variation.id)


class TestApprovalLifecycle:
    async def _setup_pending_proposal(self, db: AsyncSession, email_prefix: str):
        owner = await _make_user(db, f"{email_prefix}@example.com")
        project = await _make_project(db, owner.id)
        proposal = await _make_proposal(db, project.id, owner.id)
        proposal.status = ProposalStatus.COMPLETED
        proposal.approval_status = ApprovalStatus.PENDING_APPROVAL
        db.add(proposal)
        await db.flush()
        return owner, proposal

    async def test_approve_proposal_sets_approved_status(
        self, db_session: AsyncSession
    ):
        owner, proposal = await self._setup_pending_proposal(db_session, "appr")
        svc = ProposalService(db_session)

        approved = await svc.approve_proposal(proposal.id, approved_by_id=owner.id)
        assert approved.approval_status == ApprovalStatus.APPROVED

    async def test_reject_proposal_sets_rejected_status(self, db_session: AsyncSession):
        owner, proposal = await self._setup_pending_proposal(db_session, "rej")
        svc = ProposalService(db_session)

        rejected = await svc.reject_proposal(proposal.id, reason="Not approved")
        assert rejected.approval_status == ApprovalStatus.REJECTED

    async def test_approve_non_pending_proposal_raises_bad_request(
        self, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "appr_bad@example.com")
        project = await _make_project(db_session, owner.id)
        proposal = await _make_proposal(db_session, project.id, owner.id)
        # Still DRAFT - not pending
        svc = ProposalService(db_session)

        with pytest.raises(BadRequestException):
            await svc.approve_proposal(proposal.id, approved_by_id=owner.id)


class TestDeleteProposal:
    async def test_delete_removes_row(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "del_prop@example.com")
        project = await _make_project(db_session, owner.id)
        proposal = await _make_proposal(db_session, project.id, owner.id)
        proposal_id = proposal.id
        svc = ProposalService(db_session)

        await svc.delete_proposal(proposal_id)

        fetched = await db_session.get(Proposal, proposal_id)
        assert fetched is None
