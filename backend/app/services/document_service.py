"""
Document service for historical document management and RAG pipeline.

Handles:
    - Document upload (PDF, DOCX, TXT, MD)
    - Text extraction via parsers
    - Vectorization task dispatching
    - Document lifecycle (pending → processing → processed/failed)
    - Access control (owner + project members)
    - CRUD operations

Flow:
    1. User uploads file → extract text → save HistoricalDocument
    2. Dispatch Celery task for vectorization
    3. Task chunks text → generates embeddings → saves DocumentChunks
    4. Document status updated throughout process
"""

import structlog
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.project import Project, HistoricalDocument, DocumentStatus
from app.models.user import UserRole
from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    DocumentProcessingException,
)
from app.core.parsers import extract_text_from_file, validate_file_extension
from app.services.vector_service import VectorService

logger = structlog.get_logger()


class DocumentService:
    """
    Service for managing historical documents and RAG pipeline.

    All methods require AsyncSession and enforce project-level access control.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.vector_service = VectorService(session=session)

    # ==================== Upload ====================

    async def upload_document(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
        file: UploadFile,
    ) -> HistoricalDocument:
        """
        Upload and process a historical document.

        Flow:
            1. Validate file type and size
            2. Check user has access to project
            3. Extract text from file
            4. Save HistoricalDocument record
            5. Dispatch vectorization task
            6. Update project document_count

        Args:
            project_id: Target project ID
            user_id: Uploading user ID
            user_role: User's system role
            file: Uploaded file

        Returns:
            HistoricalDocument: Created document record in PENDING status

        Raises:
            ForbiddenException: If user lacks project access
            BadRequestException: If file invalid
            DocumentProcessingException: If text extraction fails
        """
        log = logger.bind(
            operation="upload_document",
            project_id=project_id,
            filename=file.filename,
        )

        # Validate file extension
        if not validate_file_extension(file.filename):
            raise BadRequestException(
                f"Unsupported file type. Allowed: {settings.ALLOWED_UPLOAD_EXTENSIONS}"
            )

        # Check access
        await self._assert_can_access_project(project_id, user_id, user_role)

        # Extract text
        try:
            text_content = await extract_text_from_file(file)
            log.info("text_extracted", text_length=len(text_content))
        except Exception as e:
            log.error("text_extraction_failed", error=str(e))
            raise DocumentProcessingException(
                f"Failed to extract text from {file.filename}: {str(e)}"
            )

        doc = HistoricalDocument(
            filename=file.filename,
            content_text=text_content,
            file_size_bytes=len(text_content.encode("utf-8")),
            mime_type=file.content_type,
            project_id=project_id,
            uploaded_by_id=user_id,
            status=DocumentStatus.PENDING,
        )

        self.session.add(doc)

        project = await self.session.get(Project, project_id)
        if project:
            project.increment_document_count()
            self.session.add(project)

        await self.session.commit()
        await self.session.refresh(doc)

        log.info("document_created", document_id=doc.id)

        try:
            task_id = await self.vector_service.chunk_and_vectorize(
                document_id=doc.id,
                full_text=text_content,
            )
            log.info("vectorization_enqueued", celery_task_id=task_id)
        except Exception as e:
            log.error("vectorization_dispatch_failed", error=str(e))

        return doc

    # ==================== Read ====================

    async def get_document_by_id(
        self,
        document_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> HistoricalDocument:
        """
        Get a single document by ID with access control.

        Raises:
            NotFoundException: If document not found
            ForbiddenException: If user lacks access to parent project
        """
        doc = await self.session.get(HistoricalDocument, document_id)
        if not doc:
            raise NotFoundException(f"Document {document_id} not found")

        await self._assert_can_access_project(doc.project_id, user_id, user_role)

        return doc

    async def get_project_documents(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
        status: Optional[DocumentStatus] = None,
        limit: int = 50,
    ) -> List[HistoricalDocument]:
        """
        Get all documents for a project with optional status filter.

        Args:
            project_id: Target project ID
            user_id: Requesting user ID
            user_role: User's system role
            status: Optional status filter
            limit: Max results to return

        Returns:
            List[HistoricalDocument]: Project documents

        Raises:
            ForbiddenException: If user lacks access
        """
        await self._assert_can_access_project(project_id, user_id, user_role)

        query = select(HistoricalDocument).where(
            HistoricalDocument.project_id == project_id
        )

        if status:
            query = query.where(HistoricalDocument.status == status)

        query = query.order_by(HistoricalDocument.upload_date.desc()).limit(limit)

        result = await self.session.exec(query)
        return result.all()

    # ==================== Update ====================

    async def update_document_status(
        self,
        document_id: int,
        status: DocumentStatus,
        error_message: Optional[str] = None,
    ) -> HistoricalDocument:
        """
        Update document processing status.

        Called by vectorization task to track progress.
        Should not be exposed as a public API endpoint.

        Args:
            document_id: Document ID
            status: New status
            error_message: Optional error message if status is FAILED

        Returns:
            HistoricalDocument: Updated document

        Raises:
            NotFoundException: If document not found
        """
        doc = await self.session.get(HistoricalDocument, document_id)
        if not doc:
            raise NotFoundException(f"Document {document_id} not found")

        doc.status = status
        if error_message:
            doc.error_message = error_message
        elif status == DocumentStatus.COMPLETED:
            doc.error_message = None

        doc.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)

        logger.info(
            "document_status_updated",
            document_id=document_id,
            status=status.value,
        )

        return doc

    # ==================== Delete ====================

    async def delete_document(
        self,
        document_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Delete a document and its associated chunks.

        Args:
            document_id: Document ID to delete
            user_id: Requesting user ID
            user_role: User's system role

        Raises:
            NotFoundException: If document not found
            ForbiddenException: If user lacks access
        """
        doc = await self.get_document_by_id(document_id, user_id, user_role)

        # Delete chunks first (foreign key constraint)
        await self.vector_service.delete_document_chunks(document_id)

        # Delete document
        await self.session.delete(doc)

        # Decrement project document count
        project = await self.session.get(Project, doc.project_id)
        if project and project.document_count > 0:
            project.document_count -= 1
            project.update_activity()
            self.session.add(project)

        await self.session.commit()

        logger.info("document_deleted", document_id=document_id)

    # ==================== Retry ====================

    async def retry_failed_document(
        self,
        document_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> str:
        """
        Retry vectorization for a failed document.

        Args:
            document_id: Document ID to retry
            user_id: Requesting user ID
            user_role: User's system role

        Returns:
            str: Celery task ID

        Raises:
            NotFoundException: If document not found
            ForbiddenException: If user lacks access
            BadRequestException: If document is not in FAILED status
        """
        doc = await self.get_document_by_id(document_id, user_id, user_role)

        if doc.status != DocumentStatus.FAILED:
            raise BadRequestException(
                f"Cannot retry document with status '{doc.status.value}'. "
                "Only FAILED documents can be retried."
            )

        # Reset status
        doc.status = DocumentStatus.PENDING
        doc.error_message = None
        doc.indexing_progress = 0
        self.session.add(doc)
        await self.session.commit()

        # Re-dispatch vectorization
        task_id = await self.vector_service.chunk_and_vectorize(
            document_id=doc.id,
            full_text=doc.content_text,
        )

        logger.info(
            "document_retry_enqueued",
            document_id=document_id,
            celery_task_id=task_id,
        )

        return task_id

    # ==================== Access Control ====================

    async def _assert_can_access_project(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Assert user has access to a project.

        Reuses project_service access control logic.

        Raises:
            ForbiddenException: If user lacks access
        """
        from app.services.project_service import ProjectService

        project_service = ProjectService(self.session)

        try:
            # This will raise NotFoundException if project doesn't exist
            # or user doesn't have access
            await project_service.get_project_by_id(
                project_id=project_id,
                user_id=user_id,
                user_role=user_role,
            )
        except NotFoundException:
            # Re-raise as ForbiddenException to avoid revealing project existence
            raise ForbiddenException(
                "You do not have access to this project or it does not exist"
            )
