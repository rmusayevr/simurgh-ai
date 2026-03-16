"""
Proposal endpoints for AI-generated proposal management.

Provides:
    - Create draft proposals
    - Upload supporting documents
    - Execute proposals (trigger AI generation)
    - Retrieve proposals and variations
    - Chat with personas about their proposals
    - Select winning variation
    - Export to PDF/Jira/Confluence
    - Retry failed proposals

Workflow:
    1. Create draft (POST /draft)
    2. Upload documents (POST /{id}/documents)
    3. Execute (POST /{id}/execute) → Triggers Celery task
    4. Poll status (GET /{id})
    5. Chat with personas (POST /variations/{id}/chat)
    6. Select variation (POST /{id}/select_strategy)
    7. Export (GET /{id}/export_pdf)

ROUTE ORDERING NOTE:
    FastAPI matches routes in registration order. Static path segments must be
    registered BEFORE parameterized ones to avoid shadowing. Order matters:
        /draft          → before /{proposal_id}
        /project/{id}   → before /{proposal_id}
        /variations/... → before /{proposal_id}
"""

from fastapi.params import Body
import structlog
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Query

# from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user, PaginationParams
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from app.models.user import User
from app.models.proposal import ProposalStatus
from app.schemas.proposal import (
    ProposalCreateDraft,
    ProposalRead,
    ProposalListRead,
    ChatRequest,
    ChatResponse,
    SelectVariationRequest,
)
from app.services.proposal_service import ProposalService

logger = structlog.get_logger()
router = APIRouter()


# ==================== Create Draft ====================
# IMPORTANT: /draft must be registered BEFORE /{proposal_id} to avoid shadowing.


@router.post("/draft", response_model=ProposalRead, status_code=201)
@router.post("/", response_model=ProposalRead, status_code=201)
async def create_draft_proposal(
    proposal_data: ProposalCreateDraft,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new draft proposal.

    Accepts both POST /proposals/ and POST /proposals/draft (frontend uses /draft).

    Args:
        proposal_data: Proposal details (project_id, task_description)

    Returns:
        ProposalRead: Created draft proposal (status: DRAFT)

    Raises:
        ForbiddenException: If user lacks project access
        BadRequestException: If validation fails
    """
    log = logger.bind(
        operation="create_draft",
        project_id=proposal_data.project_id,
    )

    proposal_service = ProposalService(session)

    proposal = await proposal_service.create_proposal(
        project_id=proposal_data.project_id,
        task_description=proposal_data.task_description,
        created_by_id=current_user.id,
    )

    log.info("draft_created", proposal_id=proposal.id)
    return proposal


@router.patch("/{proposal_id}/draft", response_model=ProposalRead)
async def update_draft_proposal(
    proposal_id: int,
    update_data: dict,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Update a draft proposal's task description.

    Only allowed while the proposal is still in DRAFT status.

    Args:
        proposal_id: Proposal ID
        update_data: Dict with optional 'task_description' key

    Returns:
        ProposalRead: Updated proposal

    Raises:
        NotFoundException: If proposal not found
        BadRequestException: If proposal is not in DRAFT status
    """
    from app.models.proposal import Proposal as ProposalModel, ProposalStatus as PS
    from datetime import datetime, timezone

    log = logger.bind(operation="update_draft", proposal_id=proposal_id)

    proposal = await session.get(ProposalModel, proposal_id)
    if not proposal:
        raise NotFoundException(f"Proposal {proposal_id} not found")
    if proposal.status != PS.DRAFT:
        raise BadRequestException("Only DRAFT proposals can be edited")

    new_description = (update_data.get("task_description") or "").strip()
    if not new_description or len(new_description) < 10:
        raise BadRequestException("task_description must be at least 10 characters")

    proposal.task_description = new_description
    proposal.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(proposal)
    await session.commit()
    await session.refresh(proposal)

    log.info("draft_updated", proposal_id=proposal_id)
    return proposal


# ==================== Upload Documents ====================


@router.post("/{proposal_id}/documents", response_model=ProposalRead)
async def upload_supporting_document(
    proposal_id: int,
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Upload a supporting document (PDF) to a draft proposal.

    Only PDFs are supported. Document content is extracted and attached.

    Args:
        proposal_id: Proposal ID
        file: PDF file to upload

    Returns:
        ProposalRead: Updated proposal with new document

    Raises:
        NotFoundException: If proposal not found
        ForbiddenException: If user lacks access
        BadRequestException: If not PDF or proposal not DRAFT
    """
    log = logger.bind(operation="upload_document", proposal_id=proposal_id)

    proposal_service = ProposalService(session)

    try:
        proposal = await proposal_service.add_task_document(
            proposal_id=proposal_id,
            user_id=current_user.id,
            user_role=current_user.role,
            file=file,
        )

        log.info("document_uploaded", filename=file.filename)
        return proposal

    except (NotFoundException, BadRequestException, ForbiddenException):
        raise
    except Exception as e:
        log.error("document_upload_failed", error=str(e))
        raise BadRequestException(f"Document upload failed: {str(e)}")


@router.delete("/{proposal_id}/documents/{document_id}", status_code=204)
async def delete_task_document(
    proposal_id: int,
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Remove a supporting document from a draft proposal.

    Only works while the proposal is in DRAFT status. Once generation
    has started the document set is locked.

    Args:
        proposal_id: Proposal ID
        document_id: TaskDocument ID to delete

    Returns:
        204 No Content

    Raises:
        NotFoundException: If proposal or document not found
        ForbiddenException: If user lacks access
        BadRequestException: If proposal is not in DRAFT status
    """
    proposal_service = ProposalService(session)

    try:
        await proposal_service.delete_task_document(
            proposal_id=proposal_id,
            document_id=document_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
        logger.info(
            "task_document_deleted",
            proposal_id=proposal_id,
            document_id=document_id,
        )
        return None

    except (NotFoundException, BadRequestException, ForbiddenException):
        raise


# ==================== Execute Proposal ====================


@router.post("/{proposal_id}/execute")
async def execute_proposal(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Execute a draft proposal (trigger AI generation).

    Enqueues Celery task to generate multi-agent council proposals.

    Args:
        proposal_id: Proposal ID

    Returns:
        dict: Execution status with Celery task ID

    Raises:
        NotFoundException: If proposal not found
        ForbiddenException: If user lacks access
        BadRequestException: If proposal not DRAFT or invalid
    """
    log = logger.bind(operation="execute_proposal", proposal_id=proposal_id)

    proposal_service = ProposalService(session)

    try:
        celery_task_id = await proposal_service.execute_proposal(
            proposal_id=proposal_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )

        log.info("proposal_executed", celery_task_id=celery_task_id)

        return {
            "status": "processing",
            "celery_task_id": celery_task_id,
            "message": "AI council is analyzing your task. This may take 1-2 minutes.",
        }

    except (NotFoundException, BadRequestException, ForbiddenException):
        raise
    except Exception as e:
        log.error("execution_failed", error=str(e))
        raise BadRequestException(f"Execution failed: {str(e)}")


@router.post("/{proposal_id}/retry")
async def retry_failed_proposal(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Retry a failed proposal.

    Only works for proposals with FAILED status.

    Args:
        proposal_id: Proposal ID

    Returns:
        dict: Retry status with Celery task ID

    Raises:
        NotFoundException: If proposal not found
        ForbiddenException: If user lacks access
        BadRequestException: If proposal status is not FAILED
    """
    log = logger.bind(operation="retry_proposal", proposal_id=proposal_id)

    proposal_service = ProposalService(session)

    try:
        celery_task_id = await proposal_service.retry_failed_proposal(proposal_id)

        log.info("proposal_retry_enqueued", celery_task_id=celery_task_id)

        return {
            "status": "processing",
            "celery_task_id": celery_task_id,
            "message": "Proposal is being retried",
        }

    except (NotFoundException, BadRequestException):
        raise
    except Exception as e:
        log.error("retry_failed", error=str(e))
        raise BadRequestException(f"Retry failed: {str(e)}")


# ==================== Retrieve Proposals ====================
@router.get("/project/{project_id}/active", response_model=List[ProposalRead])
async def list_active_project_proposals(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    List active (DRAFT + PROCESSING) proposals for a project.

    Used by the frontend hook to populate the Mission Lobby and
    drive the proposal poller. Returns full ProposalRead objects
    (including variations and documents) so the War Room can render
    immediately without a second fetch.

    Args:
        project_id: Project ID

    Returns:
        List[ProposalRead]: Active proposals ordered by created_at desc
    """
    proposal_service = ProposalService(session)

    proposals = await proposal_service.get_proposals_by_project(
        project_id=project_id,
        limit=50,
    )

    active = [
        p
        for p in proposals
        if p.status in (ProposalStatus.DRAFT, ProposalStatus.PROCESSING)
    ]

    return active


@router.get("/project/{project_id}", response_model=List[ProposalListRead])
async def list_project_proposals(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(),
    status: Optional[ProposalStatus] = Query(default=None),
):
    """
    List all proposals for a project (lightweight, for history view).

    Args:
        project_id: Project ID
        status: Optional status filter
        pagination: Skip/limit params

    Returns:
        List[ProposalListRead]: Project proposals

    Raises:
        ForbiddenException: If user lacks project access
    """
    proposal_service = ProposalService(session)

    proposals = await proposal_service.get_proposals_by_project(
        project_id=project_id,
        status=status,
        limit=pagination.limit,
    )

    return proposals


@router.get("/{proposal_id}", response_model=ProposalRead)
async def get_proposal(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get a specific proposal with all variations and documents.

    Args:
        proposal_id: Proposal ID

    Returns:
        ProposalRead: Full proposal details

    Raises:
        NotFoundException: If proposal not found or user lacks access
    """
    proposal_service = ProposalService(session)

    proposal = await proposal_service.get_by_id(
        proposal_id=proposal_id,
    )

    return proposal


# ==================== Persona Chat ====================


@router.post("/variations/{variation_id}/chat", response_model=ChatResponse)
async def chat_with_persona(
    variation_id: int,
    chat_request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Chat with a persona about their proposal.

    The persona defends and explains their architectural decisions.
    The user message is saved to persistent chat history, the AI
    generates a reply (also saved), and the full ChatResponse is returned.

    Args:
        variation_id: Variation ID
        chat_request: User message (+ optional history override)

    Returns:
        ChatResponse: AI response with updated history

    Raises:
        NotFoundException: If variation not found
        BadRequestException: If message is empty
    """
    from app.services.ai import ai_service

    log = logger.bind(operation="persona_chat", variation_id=variation_id)

    proposal_service = ProposalService(session)

    try:
        # 1. Fetch variation (raises NotFoundException if missing)
        variation = await proposal_service.get_variation_by_id(variation_id)

        # 2. Build history for the AI call — use DB history, not client-sent history
        #    (prevents history tampering; client history param is ignored)
        existing_history = variation.chat_history or []

        # 3. Call Claude — persona defends their proposal
        ai_response, updated_history = await ai_service.chat_with_persona(
            persona_name=variation.agent_persona.value.replace("_", " ").title(),
            proposal_content=variation.structured_prd,
            original_task="",  # structured_prd contains the full context
            user_message=chat_request.message,
            history=existing_history,
        )

        # 4. Persist both the user turn and AI reply to the DB
        variation.add_chat_message(role="user", content=chat_request.message)
        variation.add_chat_message(role="assistant", content=ai_response)
        session.add(variation)
        await session.commit()
        await session.refresh(variation)

        log.info("persona_chat_success", history_length=len(variation.chat_history))

        return ChatResponse(
            response=ai_response,
            reasoning=variation.reasoning,
            trade_offs=variation.trade_offs,
            confidence_score=variation.confidence_score,
            updated_history=variation.chat_history,
        )

    except (NotFoundException, BadRequestException, ForbiddenException):
        raise
    except Exception as e:
        log.error("chat_failed", error=str(e))
        raise BadRequestException(f"Chat failed: {str(e)}")


# ==================== Select Variation ====================


@router.post("/{proposal_id}/select")
async def select_variation(
    proposal_id: int,
    selection: SelectVariationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Select a winning variation.

    Locks in the chosen architectural strategy.

    Args:
        proposal_id: Proposal ID
        selection: Variation ID to select

    Returns:
        dict: Success message with selected variation details

    Raises:
        NotFoundException: If proposal or variation not found
        ForbiddenException: If user lacks access
        BadRequestException: If proposal not COMPLETED
    """
    log = logger.bind(operation="select_variation", proposal_id=proposal_id)

    proposal_service = ProposalService(session)

    try:
        await proposal_service.select_variation(
            proposal_id=proposal_id,
            variation_id=selection.variation_id,
        )

        log.info("variation_selected", variation_id=selection.variation_id)

        return {
            "success": True,
            "selected_id": selection.variation_id,
            "message": "Variation selected successfully",
        }

    except (NotFoundException, BadRequestException, ForbiddenException):
        raise
    except Exception as e:
        log.error("selection_failed", error=str(e))
        raise BadRequestException(f"Selection failed: {str(e)}")


# ==================== Delete ====================


@router.delete("/{proposal_id}", status_code=204)
async def delete_proposal(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a proposal and all associated data.

    Only project owner can delete.

    Args:
        proposal_id: Proposal ID

    Returns:
        None (204 No Content)

    Raises:
        NotFoundException: If proposal not found
        ForbiddenException: If user is not project owner
    """
    proposal_service = ProposalService(session)

    await proposal_service.delete_proposal(
        proposal_id=proposal_id,
    )

    logger.info("proposal_deleted", proposal_id=proposal_id)
    return None


# ==================== Jira Export ====================


@router.post("/{proposal_id}/export/jira")
async def export_to_jira(
    proposal_id: int,
    jira_project_key: str = Body(..., embed=True),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Export a proposal to Jira as an epic with child stories.

    Uses the user's stored Atlassian OAuth credential automatically.
    Falls back to JIRA_DEFAULT_* env vars for non-Atlassian-auth users.

    The selected variation is exported. If no variation is selected,
    the highest-confidence variation is used.

    Args:
        proposal_id:      Proposal to export
        jira_project_key: Target Jira project key (e.g. "PROJ")

    Returns:
        dict: epic_key, epic_url, stories list
    """
    from app.services.jira_adapter import JiraAdapter

    log = logger.bind(operation="export_jira", proposal_id=proposal_id)

    proposal_service = ProposalService(session)
    proposal = await proposal_service.get_by_id(proposal_id)

    if not proposal.variations:
        raise BadRequestException("Proposal has no generated variations to export.")

    # Use selected variation, otherwise highest confidence
    variation = None
    if proposal.selected_variation_id:
        variation = next(
            (v for v in proposal.variations if v.id == proposal.selected_variation_id),
            None,
        )
    if not variation:
        variation = max(proposal.variations, key=lambda v: v.confidence_score)

    adapter = JiraAdapter(db=session, user_id=current_user.id)

    try:
        result = await adapter.export_proposal(
            proposal=proposal,
            variation=variation,
            jira_project_key=jira_project_key,
        )
        log.info("jira_export_success", epic_key=result["epic_key"])
        return result

    except BadRequestException:
        raise
    except Exception as e:
        log.error("jira_export_failed", error=str(e))
        raise BadRequestException(f"Jira export failed: {str(e)}")


@router.get("/{proposal_id}/jira/status")
async def get_jira_export_status(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Return the Jira export status for a proposal.

    Used by the frontend to show the 'already exported' state.
    """
    proposal_service = ProposalService(session)
    proposal = await proposal_service.get_by_id(proposal_id)

    return {
        "exported": proposal.jira_epic_key is not None,
        "epic_key": proposal.jira_epic_key,
        "epic_url": proposal.jira_epic_url,
        "project_key": proposal.jira_project_key,
        "exported_at": (
            proposal.jira_exported_at.isoformat() if proposal.jira_exported_at else None
        ),
    }


# ==================== Confluence Export ====================


@router.post("/{proposal_id}/export/confluence")
async def export_to_confluence(
    proposal_id: int,
    space_key: str = Body(..., embed=True),
    preset: str = Body("internal_tech_review", embed=True),
    parent_page_id: str = Body(None, embed=True),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Export a proposal to Confluence as a structured page.

    Three presets control content depth:
        internal_tech_review  — Full: architecture, risks, trade-offs, reasoning
        executive_presentation — Executive summary + risks + timeline only
        public_documentation  — Architecture spec only, no internal data

    The selected variation is used. Falls back to highest-confidence variation.

    Args:
        proposal_id:    Proposal to export
        space_key:      Target Confluence space key (e.g. "ARCH")
        preset:         Export preset name
        parent_page_id: Optional parent page ID to nest the new page under
    """
    from app.services.confluence_adapter import ConfluenceAdapter, ExportPreset

    log = logger.bind(operation="export_confluence", proposal_id=proposal_id)

    # Validate preset
    try:
        export_preset = ExportPreset(preset)
    except ValueError:
        raise BadRequestException(
            f"Invalid preset '{preset}'. "
            f"Choose from: internal_tech_review, executive_presentation, public_documentation"
        )

    proposal_service = ProposalService(session)
    proposal = await proposal_service.get_by_id(proposal_id)

    if not proposal.variations:
        raise BadRequestException("Proposal has no generated variations to export.")

    variation = None
    if proposal.selected_variation_id:
        variation = next(
            (v for v in proposal.variations if v.id == proposal.selected_variation_id),
            None,
        )
    if not variation:
        variation = max(proposal.variations, key=lambda v: v.confidence_score)

    adapter = ConfluenceAdapter(db=session, user_id=current_user.id)

    try:
        result = await adapter.export_proposal(
            proposal=proposal,
            variation=variation,
            space_key=space_key,
            preset=export_preset,
            parent_page_id=parent_page_id or None,
        )
        log.info("confluence_export_success", page_id=result["page_id"])
        return result

    except BadRequestException:
        raise
    except Exception as e:
        log.error("confluence_export_failed", error=str(e))
        raise BadRequestException(f"Confluence export failed: {str(e)}")


@router.get("/{proposal_id}/confluence/status")
async def get_confluence_export_status(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: AsyncSession = Depends(get_session),
):
    """Return Confluence export status for a proposal."""
    proposal_service = ProposalService(session)
    proposal = await proposal_service.get_by_id(proposal_id)

    return {
        "exported": proposal.confluence_page_id is not None,
        "page_id": proposal.confluence_page_id,
        "page_url": proposal.confluence_page_url,
        "space_key": proposal.confluence_space_key,
        "exported_at": (
            proposal.confluence_exported_at.isoformat()
            if proposal.confluence_exported_at
            else None
        ),
    }


# ==================== PDF Export ====================


@router.get("/{proposal_id}/export/pdf")
async def export_to_pdf(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Export the selected (or highest-confidence) proposal variation as a PDF.

    Returns a downloadable PDF file with:
      - Cover page: persona badge, task description, confidence score, metadata
      - Architecture specification from the PRD (markdown rendered)
      - Reasoning & trade-offs section
      - Document information footer page

    The PDF filename is sanitised from the proposal task description.
    """
    from fastapi.responses import Response
    from app.services.pdf_generator import generate_proposal_pdf
    from app.models.project import Project

    log = logger.bind(operation="export_pdf", proposal_id=proposal_id)

    proposal_service = ProposalService(session)
    proposal = await proposal_service.get_by_id(proposal_id)

    if not proposal.variations:
        raise BadRequestException("Proposal has no generated variations to export.")

    # Use selected variation, otherwise highest confidence
    variation = None
    if proposal.selected_variation_id:
        variation = next(
            (v for v in proposal.variations if v.id == proposal.selected_variation_id),
            None,
        )
    if not variation:
        variation = max(proposal.variations, key=lambda v: v.confidence_score)

    # Fetch project name for the cover page
    project = await session.get(Project, proposal.project_id)
    project_name = project.name if project else f"Project {proposal.project_id}"

    try:
        pdf_bytes = generate_proposal_pdf(
            proposal=proposal,
            variation=variation,
            project_name=project_name,
        )
    except Exception as e:
        log.error("pdf_generation_failed", error=str(e))
        raise BadRequestException(f"PDF generation failed: {str(e)}")

    # Build a clean filename from the task description
    import re as _re

    safe_name = _re.sub(r"[^a-zA-Z0-9]+", "_", proposal.task_description[:50]).strip(
        "_"
    )
    filename = f"SimurghAI_{safe_name}_{proposal_id}.pdf"

    log.info("pdf_export_success", proposal_id=proposal_id, size=len(pdf_bytes))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
