"""
Admin - Proposal management endpoints.

GET /admin/proposals
PATCH /admin/proposals/{proposal_id}/status
DELETE /admin/proposals/{proposal_id}
"""

import structlog
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_superuser, PaginationParams
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.models.project import Project
from app.models.proposal import Proposal, ProposalStatus
from app.services.proposal_service import ProposalService

logger = structlog.get_logger()
router = APIRouter()


@router.get("/proposals")
async def list_all_proposals(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(),
    status: Optional[ProposalStatus] = None,
):
    """
    List all proposals across all projects.
    """
    query = (
        select(Proposal, Project.name, User.email)
        .join(Project, Proposal.project_id == Project.id)
        .join(User, Project.owner_id == User.id)
        .order_by(Proposal.created_at.desc())
    )

    if status:
        query = query.where(Proposal.status == status)

    query = query.offset(pagination.skip).limit(pagination.limit)

    results = await session.exec(query)

    proposals = []
    for prop, proj_name, owner_email in results:
        proposals.append(
            {
                "id": prop.id,
                "task_description": prop.task_description,
                "status": prop.status.value,
                "approval_status": (
                    prop.approval_status.value if prop.approval_status else None
                ),
                "project_name": proj_name,
                "owner_email": owner_email,
                "created_at": prop.created_at.isoformat(),
            }
        )

    return proposals


@router.patch("/proposals/{proposal_id}/status")
async def override_proposal_status(
    proposal_id: int,
    status: ProposalStatus,
    session: AsyncSession = Depends(get_session),
):
    """
    Admin override of proposal status.
    """
    proposal = await session.get(Proposal, proposal_id)
    if not proposal:
        raise NotFoundException(f"Proposal {proposal_id} not found")

    old_status = proposal.status
    proposal.status = status
    proposal.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    session.add(proposal)
    await session.commit()

    logger.warning(
        "admin_status_override",
        proposal_id=proposal_id,
        old_status=old_status.value,
        new_status=status.value,
    )

    return {
        "proposal_id": proposal_id,
        "old_status": old_status.value,
        "new_status": status.value,
    }


@router.delete("/proposals/{proposal_id}")
async def delete_proposal(
    proposal_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_superuser),
):
    """
    Delete a proposal and all variations (cascade).
    """
    proposal_service = ProposalService(session)

    await proposal_service.delete_proposal(proposal_id)

    return {
        "success": True,
        "message": "Proposal and all variations deleted",
    }
