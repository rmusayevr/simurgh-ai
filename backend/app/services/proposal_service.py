"""
Proposal Service for managing architecture proposals.

Handles all business logic related to proposals:
    - Draft creation and lifecycle management
    - Variation management and selection
    - Approval workflow (submit, approve, reject, revise)
    - Chat history per variation (Deep-Dive Debate Mode)

RESEARCH WORKFLOW (3 DISTINCT PROPOSALS):
    1. Debate happens → 3 personas discuss architectural trade-offs
    2. Each persona generates THEIR OWN proposal → 3 ProposalVariation records
    3. Human selects ONE → POST /proposals/{id}/select
"""

import io

import pypdf
from app.services.proposal_tasks import generate_proposal_content_task
from fastapi import UploadFile
import structlog
from datetime import datetime, timezone

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Optional

from app.core.exceptions import NotFoundException, BadRequestException
from app.models.proposal import (
    Proposal,
    ProposalStatus,
    ApprovalStatus,
    ProposalVariation,
    TaskDocument,
)
from app.models.project import Project
from app.services.vector_service import VectorService


logger = structlog.get_logger()


class ProposalService:
    """
    Service for managing proposals and their lifecycle.

    RESEARCH WORKFLOW:
        1. Create draft proposal
        2. Execute → Generates 3 DISTINCT proposals (one per persona)
        3. Human selects winning variation
        4. Approval workflow (optional)

    Covers:
        - Creation and Celery task enqueueing
        - Retrieval (single, list, variation)
        - Variation selection (RQ1: human chooses best proposal)
        - Approval workflow
        - Chat history management (Deep-Dive Debate Mode)
        - Retry and deletion
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.vector_service = VectorService(session=session)

    # ==================== Create ====================

    async def create_proposal(
        self,
        project_id: int,
        task_description: str,
        created_by_id: int,
        files: List[tuple[str, str]] = [],
    ) -> Proposal:
        """
        Create a new proposal draft and enqueue it for AI generation.

        Updates project's cached proposal_count.

        Args:
            project_id: Parent project ID
            task_description: The architectural task/problem to solve
            created_by_id: ID of the requesting user
            files: List of (filename, content_text) tuples for task documents

        Returns:
            Created Proposal in PROCESSING state

        Raises:
            BadRequestException: If task_description is empty or too long
        """
        log = logger.bind(
            operation="create_proposal",
            project_id=project_id,
            created_by_id=created_by_id,
        )

        task_description = task_description.strip()
        if not task_description:
            raise BadRequestException("Task description cannot be empty")
        if len(task_description) > 50000:
            raise BadRequestException(
                "Task description too long (max 50,000 characters)"
            )

        # Create in DRAFT first
        proposal = Proposal(
            project_id=project_id,
            task_description=task_description,
            created_by_id=created_by_id,
            status=ProposalStatus.DRAFT,
            approval_status=ApprovalStatus.DRAFT,
        )
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)

        log.info("proposal_draft_created", proposal_id=proposal.id)

        # Attach task-specific documents
        if files:
            for filename, text in files:
                if not filename or not text:
                    log.warning("skipping_empty_document", filename=filename)
                    continue

                doc = TaskDocument(
                    filename=filename,
                    content_text=text,
                    proposal_id=proposal.id,
                    uploader_id=created_by_id,
                )
                self.session.add(doc)

            await self.session.commit()
            log.info("task_documents_saved", count=len(files))

        # Update project's cached proposal count
        project = await self.session.get(Project, project_id)
        if project:
            project.increment_proposal_count()
            self.session.add(project)

        await self.session.commit()

        return proposal

    # ==================== Read ====================

    async def get_by_id(self, proposal_id: int) -> Proposal:
        """
        Fetch a proposal by ID with all 3 variations loaded.

        Returns ProposalRead with variations list containing 3 items.

        Raises:
            NotFoundException: If proposal not found
        """
        statement = (
            select(Proposal)
            .where(Proposal.id == proposal_id)
            .options(
                selectinload(Proposal.variations),
                selectinload(Proposal.task_documents).selectinload(
                    TaskDocument.uploader
                ),
                selectinload(Proposal.debate_sessions),
            )
            .execution_options(populate_existing=True)
        )

        result = await self.session.exec(statement)
        proposal = result.first()

        if not proposal:
            raise NotFoundException(f"Proposal {proposal_id} not found")

        return proposal

    async def get_proposals_by_project(
        self,
        project_id: int,
        status: Optional[ProposalStatus] = None,
        approval_status: Optional[ApprovalStatus] = None,
        limit: int = 50,
    ) -> List[Proposal]:
        """
        Get all proposals for a project with optional status filtering.

        Each proposal contains 3 variations (legacy_keeper, innovator, mediator).

        Args:
            project_id: Parent project ID
            status: Filter by generation status
            approval_status: Filter by approval workflow status
            limit: Max results to return

        Returns:
            List of proposals ordered by created_at desc
        """
        statement = select(Proposal).where(Proposal.project_id == project_id)

        if status:
            statement = statement.where(Proposal.status == status)
        if approval_status:
            statement = statement.where(Proposal.approval_status == approval_status)

        statement = (
            statement.options(
                selectinload(Proposal.variations),
                selectinload(Proposal.task_documents).selectinload(
                    TaskDocument.uploader
                ),
            )
            .order_by(Proposal.created_at.desc())
            .limit(limit)
        )

        result = await self.session.exec(statement)
        proposals = result.unique().all()

        logger.info(
            "proposals_retrieved",
            project_id=project_id,
            count=len(proposals),
        )
        return list(proposals)

    async def get_variation_by_id(self, variation_id: int) -> ProposalVariation:
        """
        Fetch a specific proposal variation.

        Raises:
            NotFoundException: If variation not found
        """
        variation = await self.session.get(ProposalVariation, variation_id)
        if not variation:
            raise NotFoundException(f"Variation {variation_id} not found")
        return variation

    # ==================== Variation Selection (RQ1 EVALUATION) ====================

    async def select_variation(
        self,
        proposal_id: int,
        variation_id: int,
    ) -> Proposal:
        """
        Select a variation as the winning proposal (RQ1: Human chooses best).

        This is the key decision point in the research study:
        Participants compare 3 proposals and select their preferred approach.

        Validates the variation belongs to this proposal.

        Raises:
            NotFoundException: If proposal or variation not found
            BadRequestException: If variation doesn't belong to this proposal
        """
        proposal = await self.get_by_id(proposal_id)
        variation = await self.get_variation_by_id(variation_id)

        if variation.proposal_id != proposal_id:
            raise BadRequestException("Variation does not belong to this proposal")

        proposal.selected_variation_id = variation_id
        proposal.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)

        logger.info(
            "variation_selected_for_rq1",
            proposal_id=proposal_id,
            variation_id=variation_id,
            persona=variation.agent_persona.value,
        )
        return proposal

    # ==================== Chat (Deep-Dive Debate Mode) ====================

    async def add_chat_message(
        self,
        variation_id: int,
        role: str,
        content: str,
    ) -> ProposalVariation:
        """
        Add a message to a variation's persistent chat history.

        Used for the Deep-Dive Debate Mode feature.

        Args:
            variation_id: Target variation ID
            role: Message role ("user" or "assistant")
            content: Message content

        Returns:
            Updated ProposalVariation

        Raises:
            NotFoundException: If variation not found
        """
        variation = await self.get_variation_by_id(variation_id)
        variation.add_chat_message(role=role, content=content)
        self.session.add(variation)
        await self.session.commit()
        await self.session.refresh(variation)

        logger.info(
            "chat_message_added",
            variation_id=variation_id,
            role=role,
        )
        return variation

    # ==================== Approval Workflow ====================

    async def submit_for_approval(self, proposal_id: int) -> Proposal:
        """Submit a completed proposal for approval review."""
        proposal = await self.get_by_id(proposal_id)

        if not proposal.is_completed:
            raise BadRequestException(
                "Only completed proposals can be submitted for approval"
            )

        proposal.submit_for_approval()
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)

        logger.info("proposal_submitted_for_approval", proposal_id=proposal_id)
        return proposal

    async def approve_proposal(self, proposal_id: int, approved_by_id: int) -> Proposal:
        """Approve a submitted proposal."""
        proposal = await self.get_by_id(proposal_id)

        if proposal.approval_status != ApprovalStatus.PENDING_APPROVAL:
            raise BadRequestException("Only submitted proposals can be approved")

        proposal.approve(approved_by_id)
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)

        logger.info("proposal_approved", proposal_id=proposal_id)
        return proposal

    async def reject_proposal(self, proposal_id: int, reason: str) -> Proposal:
        """Reject a proposal with a reason."""
        proposal = await self.get_by_id(proposal_id)

        if proposal.approval_status != ApprovalStatus.PENDING_APPROVAL:
            raise BadRequestException("Only submitted proposals can be rejected")

        proposal.reject(reason)
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)

        logger.info("proposal_rejected", proposal_id=proposal_id, reason=reason)
        return proposal

    async def request_revision(self, proposal_id: int, feedback: str) -> Proposal:
        """Request revisions to a submitted proposal."""
        proposal = await self.get_by_id(proposal_id)

        if proposal.approval_status != ApprovalStatus.PENDING_APPROVAL:
            raise BadRequestException("Only submitted proposals can request revision")

        proposal.request_revision(feedback)
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)

        logger.info("proposal_revision_requested", proposal_id=proposal_id)
        return proposal

    # ==================== Delete ====================

    async def delete_proposal(self, proposal_id: int) -> None:
        """
        Delete a proposal and all associated data.

        Includes:
            - ProposalVariation records
            - TaskDocument records
            - DebateSession records
        """
        proposal = await self.get_by_id(proposal_id)

        # Delete variations
        for variation in proposal.variations:
            await self.session.delete(variation)

        # Delete task documents
        for doc in proposal.task_documents:
            await self.session.delete(doc)

        # Delete debate sessions
        for debate in proposal.debate_sessions:
            await self.session.delete(debate)

        # Delete proposal
        await self.session.delete(proposal)
        await self.session.commit()

        logger.warning("proposal_deleted", proposal_id=proposal_id)

    # ==================== Retry ====================

    async def retry_proposal(self, proposal_id: int) -> Proposal:
        """
        Retry a failed proposal by re-enqueueing the Celery task.

        Only works on FAILED proposals.
        """
        proposal = await self.get_by_id(proposal_id)

        if proposal.status != ProposalStatus.FAILED:
            raise BadRequestException("Only failed proposals can be retried")

        # Re-enqueue Celery task
        from app.services.proposal_tasks import generate_proposal_content_task

        generate_proposal_content_task.delay(proposal_id)

        # Mark as DRAFT
        proposal.status = ProposalStatus.DRAFT
        proposal.failure_reason = None
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)

        logger.info("proposal_retry_enqueued", proposal_id=proposal_id)
        return proposal

    def _enqueue_generation(self, proposal_id: int) -> str:
        """
        Enqueue the Celery task for AI council generation.

        Returns:
            str: Celery task ID
        """
        task = generate_proposal_content_task.delay(proposal_id)
        logger.info(
            "celery_task_enqueued",
            proposal_id=proposal_id,
            celery_task_id=task.id,
        )
        return task.id

    async def add_task_document(
        self,
        proposal_id: int,
        user_id: int,
        user_role: str,
        file: UploadFile,
    ) -> Proposal:
        """Extract text from a PDF and attach it as a TaskDocument to a draft proposal."""
        log = logger.bind(
            operation="service_add_document", proposal_id=proposal_id, user_id=user_id
        )

        proposal = await self.get_by_id(proposal_id)
        if proposal.status != ProposalStatus.DRAFT:
            raise BadRequestException("Documents can only be added to DRAFT proposals")

        if (
            file.content_type != "application/pdf"
            and not file.filename.lower().endswith(".pdf")
        ):
            raise BadRequestException("Only PDF files are supported")

        try:
            content = await file.read()
            pdf_reader = pypdf.PdfReader(io.BytesIO(content))
            extracted_text = ""
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
        except Exception as e:
            log.error("pdf_extraction_failed", error=str(e))
            raise BadRequestException(f"Failed to read PDF document: {str(e)}")

        if not extracted_text.strip():
            raise BadRequestException(
                "Could not extract any text from the provided PDF"
            )

        task_doc = TaskDocument(
            filename=file.filename,
            content_text=extracted_text.strip(),
            proposal_id=proposal_id,
            uploader_id=user_id,
        )

        self.session.add(task_doc)
        await self.session.commit()
        await self.session.refresh(proposal)

        log.info("document_added_to_proposal", filename=file.filename)
        return proposal

    async def delete_task_document(
        self,
        proposal_id: int,
        document_id: int,
        user_id: int,
        user_role: str,
    ) -> None:
        """
        Delete a task document from a draft proposal.

        Only allowed while the proposal is still in DRAFT status — documents
        cannot be removed after generation has started.

        Args:
            proposal_id: Proposal the document belongs to
            document_id: TaskDocument ID to delete
            user_id: Requesting user ID (for access control)
            user_role: User's system role

        Raises:
            NotFoundException: If proposal or document not found
            ForbiddenException: If user lacks access to the proposal
            BadRequestException: If proposal is not in DRAFT status
        """
        proposal = await self.get_by_id(proposal_id)

        if proposal.status != ProposalStatus.DRAFT:
            raise BadRequestException(
                "Documents can only be removed from DRAFT proposals"
            )

        doc = await self.session.get(TaskDocument, document_id)
        if not doc or doc.proposal_id != proposal_id:
            raise NotFoundException(
                f"Document {document_id} not found on proposal {proposal_id}"
            )

        await self.session.delete(doc)
        await self.session.commit()

        logger.info(
            "task_document_deleted",
            proposal_id=proposal_id,
            document_id=document_id,
        )

    # ==================== Execution ====================

    async def execute_proposal(
        self,
        proposal_id: int,
        user_id: int,
        user_role: str,
    ) -> str:
        """
        Execute a draft proposal by enqueueing the AI council generation task.

        This triggers generation of 3 DISTINCT proposals (legacy_keeper, innovator, mediator).

        Args:
            proposal_id: Proposal ID
            user_id: Requesting user ID
            user_role: Requesting user role

        Returns:
            str: Celery task ID

        Raises:
            NotFoundException: If proposal not found
            BadRequestException: If proposal is not in DRAFT status
        """
        log = logger.bind(
            operation="service_execute_proposal",
            proposal_id=proposal_id,
            user_id=user_id,
        )

        proposal = await self.get_by_id(proposal_id)

        if proposal.status != ProposalStatus.DRAFT:
            raise BadRequestException(
                f"Cannot execute proposal with status '{proposal.status.name}'. "
                "Only DRAFT proposals can be executed."
            )

        proposal.mark_processing()
        self.session.add(proposal)
        await self.session.commit()

        celery_task_id = self._enqueue_generation(proposal_id)

        log.info(
            "proposal_execution_started_for_3_variations", celery_task_id=celery_task_id
        )
        return celery_task_id
