"""
Document endpoints for historical document management and RAG pipeline.

Provides:
    - Upload documents (PDF, DOCX, TXT, MD)
    - List project documents
    - Get document details
    - Delete documents
    - Check indexing/vectorization status
    - Retry failed vectorizations

All uploads trigger background vectorization for RAG.
"""

import structlog
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    BadRequestException,
)
from app.models.user import User
from app.models.project import DocumentStatus
from app.schemas.project import (
    HistoricalDocumentRead,
    HistoricalDocumentDetail,
    DocumentIndexingStatus,
)
from app.services.document_service import DocumentService

logger = structlog.get_logger()
router = APIRouter()


# ==================== Upload ====================


@router.post(
    "/projects/{project_id}/documents",
    response_model=HistoricalDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload a historical document to a project.

    Supported formats: PDF, DOCX, TXT, MD
    Automatically triggers background vectorization for RAG.

    Args:
        project_id: Target project ID
        file: Document file to upload

    Returns:
        HistoricalDocumentRead: Uploaded document (status: PENDING)

    Raises:
        BadRequestException: If file type unsupported or too large
        ForbiddenException: If user lacks project access
    """
    log = logger.bind(
        operation="upload_document",
        project_id=project_id,
        filename=file.filename,
    )

    document_service = DocumentService(session)

    try:
        document = await document_service.upload_document(
            project_id=project_id,
            user_id=current_user.id,
            user_role=current_user.role,
            file=file,
        )

        log.info(
            "document_uploaded",
            document_id=document.id,
            status=document.status.value,
        )

        return document

    except (BadRequestException, NotFoundException, ForbiddenException):
        raise


# ==================== List & Read ====================


@router.get(
    "/projects/{project_id}/documents",
    response_model=List[HistoricalDocumentRead],
)
async def list_project_documents(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    status_filter: Optional[DocumentStatus] = Query(default=None),
):
    """
    List all documents for a project.

    Args:
        project_id: Project ID
        status_filter: Optional status filter (PENDING, PROCESSING, COMPLETED, FAILED)

    Returns:
        List[HistoricalDocumentRead]: Project documents

    Raises:
        ForbiddenException: If user lacks project access
    """
    document_service = DocumentService(session)

    documents = await document_service.get_project_documents(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
        status=status_filter,
    )

    return documents


@router.get(
    "/{document_id}",
    response_model=HistoricalDocumentDetail,
)
async def get_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get document details.

    Args:
        document_id: Document ID

    Returns:
        HistoricalDocumentDetail: Full document details

    Raises:
        NotFoundException: If document not found
        ForbiddenException: If user lacks access
    """
    document_service = DocumentService(session)

    document = await document_service.get_document_by_id(
        document_id=document_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return document


# ==================== Delete ====================


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a document and its chunks.

    Args:
        document_id: Document ID to delete

    Returns:
        None (204 No Content)

    Raises:
        NotFoundException: If document not found
        ForbiddenException: If user lacks access
    """
    document_service = DocumentService(session)

    await document_service.delete_document(
        document_id=document_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    logger.info("document_deleted", document_id=document_id)
    return None


# ==================== Vectorization Status & Retry ====================


@router.get(
    "/{document_id}/status",
    response_model=DocumentIndexingStatus,
)
async def get_indexing_status(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Check document vectorization/indexing status.

    Returns:
        - Document status (PENDING, PROCESSING, COMPLETED, FAILED)
        - Chunk count
        - Indexing progress (0-100%)
        - Error message (if failed)

    Args:
        document_id: Document ID

    Returns:
        DocumentIndexingStatus: Indexing status details

    Raises:
        NotFoundException: If document not found
        ForbiddenException: If user lacks access
    """
    document_service = DocumentService(session)

    # Verify access
    document = await document_service.get_document_by_id(
        document_id=document_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    # Build status response
    status_response = DocumentIndexingStatus(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        chunk_count=document.chunk_count or 0,
        indexing_progress=document.indexing_progress or 0,
        error_message=document.error_message,
        is_ready_for_rag=(document.status == DocumentStatus.COMPLETED),
    )

    return status_response


@router.get("/{document_id}/search-status")
async def get_search_status(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    document_service = DocumentService(session)
    doc = await document_service.get_document_by_id(
        document_id=document_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    status_map = {
        DocumentStatus.PENDING: "pending",
        DocumentStatus.PROCESSING: "processing",
        DocumentStatus.COMPLETED: "ready",
        DocumentStatus.FAILED: "failed",
    }

    return {
        "document_id": doc.id,
        "status": status_map.get(doc.status, "pending"),
        "total_chunks": doc.chunk_count or 0,
        "vector_indexed": (
            doc.chunk_count or 0
            if doc.status == DocumentStatus.COMPLETED
            else int((doc.indexing_progress or 0) / 100 * (doc.chunk_count or 0))
        ),
        "fts_indexed": (
            doc.chunk_count or 0 if doc.status == DocumentStatus.COMPLETED else 0
        ),
    }


@router.post(
    "/{document_id}/retry",
    response_model=HistoricalDocumentRead,
)
async def retry_vectorization(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Retry vectorization for a failed document.

    Only works for documents with FAILED status.

    Args:
        document_id: Document ID to retry

    Returns:
        HistoricalDocumentRead: Document with updated status (PENDING)

    Raises:
        NotFoundException: If document not found
        ForbiddenException: If user lacks access
        BadRequestException: If document status is not FAILED
    """
    log = logger.bind(operation="retry_vectorization", document_id=document_id)

    document_service = DocumentService(session)

    try:
        task_id = await document_service.retry_failed_document(
            document_id=document_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )

        log.info("vectorization_retry_enqueued", celery_task_id=task_id)

        document = await document_service.get_document_by_id(
            document_id=document_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )

        return document

    except (NotFoundException, BadRequestException):
        raise
    except Exception as e:
        log.error("retry_failed", error=str(e))
        raise BadRequestException(f"Retry failed: {str(e)}")
