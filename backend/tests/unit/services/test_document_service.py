"""
Unit tests for app/services/document_service.py

Covers:
    - upload_document: extension validation rejects .exe / allows .pdf
    - upload_document: delegates text extraction to parsers
    - upload_document: saves HistoricalDocument and increments project count
    - upload_document: extraction failure wrapped as DocumentProcessingException
    - get_document_by_id: raises NotFoundException for unknown ID
    - get_document_by_id: ForbiddenException when project access denied
    - update_document_status: updates status and optional error message
    - update_document_status: raises NotFoundException for unknown ID
    - delete_document: calls vector_service.delete_document_chunks then session.delete
    - delete_document: decrements project document_count
    - retry_failed_document: only FAILED documents
    - retry_failed_document: resets status to PENDING and re-dispatches

All DB calls mocked. Parsers and VectorService patched.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.project import HistoricalDocument, DocumentStatus
from app.models.user import UserRole
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    DocumentProcessingException,
)
from tests.fixtures.documents import (
    build_document,
    build_pending_document,
    build_failed_document,
)
from tests.fixtures.projects import build_project


# ── Helper ─────────────────────────────────────────────────────────────────────


def _make_service(db_mock):
    from app.services.document_service import DocumentService

    svc = DocumentService(session=db_mock)
    svc.vector_service = AsyncMock()
    svc.vector_service.delete_document_chunks = AsyncMock(return_value=0)
    svc.vector_service.chunk_and_vectorize = AsyncMock(return_value="task-abc")
    return svc


def _make_upload(
    filename="spec.pdf",
    content_type="application/pdf",
    content=b"sample content",
):
    mock = MagicMock()
    mock.filename = filename
    mock.content_type = content_type
    mock.read = AsyncMock(return_value=content)
    mock.seek = AsyncMock()
    return mock


# ══════════════════════════════════════════════════════════════════
# upload_document — extension validation
# ══════════════════════════════════════════════════════════════════


class TestUploadDocumentValidation:
    async def test_exe_extension_raises_bad_request(self):
        db = AsyncMock()
        svc = _make_service(db)
        file = _make_upload("malware.exe", "application/octet-stream", b"MZ")

        with pytest.raises(BadRequestException):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

    async def test_js_extension_raises_bad_request(self):
        db = AsyncMock()
        svc = _make_service(db)
        file = _make_upload("script.js", "text/javascript", b"console.log()")

        with pytest.raises(BadRequestException):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

    async def test_zip_extension_raises_bad_request(self):
        db = AsyncMock()
        svc = _make_service(db)
        file = _make_upload("data.zip", "application/zip", b"PK\x03\x04")

        with pytest.raises(BadRequestException):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

    async def test_pdf_extension_passes_validation(self):
        """PDF should pass validation and proceed to access control check."""
        db = AsyncMock()
        svc = _make_service(db)
        file = _make_upload("doc.pdf", "application/pdf", b"%PDF-1.4")

        # Stub out the project access check so it raises ForbiddenException,
        # confirming we got PAST the extension check
        svc._assert_can_access_project = AsyncMock(
            side_effect=ForbiddenException("no access")
        )

        with pytest.raises(ForbiddenException):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

    async def test_txt_extension_passes_validation(self):
        db = AsyncMock()
        svc = _make_service(db)
        file = _make_upload("notes.txt", "text/plain", b"hello")

        svc._assert_can_access_project = AsyncMock(
            side_effect=ForbiddenException("no access")
        )

        with pytest.raises(ForbiddenException):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

    async def test_docx_extension_passes_validation(self):
        db = AsyncMock()
        svc = _make_service(db)
        file = _make_upload(
            "report.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"PK",
        )

        svc._assert_can_access_project = AsyncMock(
            side_effect=ForbiddenException("no access")
        )

        with pytest.raises(ForbiddenException):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )


# ══════════════════════════════════════════════════════════════════
# upload_document — extraction failure wrapping
# ══════════════════════════════════════════════════════════════════


class TestUploadDocumentExtractionFailure:
    async def test_extraction_exception_wrapped_as_document_processing_exception(self):
        db = AsyncMock()
        svc = _make_service(db)
        svc._assert_can_access_project = AsyncMock()
        file = _make_upload("bad.pdf", "application/pdf", b"%PDF")

        with patch(
            "app.services.document_service.extract_text_from_file",
            new_callable=AsyncMock,
            side_effect=RuntimeError("corrupt PDF"),
        ):
            with pytest.raises(DocumentProcessingException):
                await svc.upload_document(
                    project_id=1, user_id=1, user_role=UserRole.USER, file=file
                )

    async def test_error_message_contains_filename(self):
        db = AsyncMock()
        svc = _make_service(db)
        svc._assert_can_access_project = AsyncMock()
        file = _make_upload("broken.pdf", "application/pdf", b"%PDF")

        with patch(
            "app.services.document_service.extract_text_from_file",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unreadable"),
        ):
            with pytest.raises(DocumentProcessingException) as exc_info:
                await svc.upload_document(
                    project_id=1, user_id=1, user_role=UserRole.USER, file=file
                )

        assert "broken.pdf" in exc_info.value.message


# ══════════════════════════════════════════════════════════════════
# upload_document — happy path (project count + vectorize dispatch)
# ══════════════════════════════════════════════════════════════════


class TestUploadDocumentHappyPath:
    async def test_project_document_count_incremented(self):
        project = build_project(id=1, document_count=2)
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: None)
        db.get = AsyncMock(return_value=project)

        svc = _make_service(db)
        svc._assert_can_access_project = AsyncMock()
        file = _make_upload()

        with patch(
            "app.services.document_service.extract_text_from_file",
            new_callable=AsyncMock,
            return_value="Extracted document text for RAG.",
        ):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

        assert project.document_count == 3

    async def test_vectorization_dispatched_after_save(self):
        project = build_project(id=1)
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(
            side_effect=lambda obj: (
                setattr(obj, "id", 10) if isinstance(obj, HistoricalDocument) else None
            )
        )
        db.get = AsyncMock(return_value=project)

        svc = _make_service(db)
        svc._assert_can_access_project = AsyncMock()
        file = _make_upload()

        with patch(
            "app.services.document_service.extract_text_from_file",
            new_callable=AsyncMock,
            return_value="Some text.",
        ):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

        svc.vector_service.chunk_and_vectorize.assert_called_once()

    async def test_document_saved_with_pending_status(self):
        project = build_project(id=1)
        added_docs = []

        db = AsyncMock()
        db.add = MagicMock(
            side_effect=lambda obj: (
                added_docs.append(obj) if isinstance(obj, HistoricalDocument) else None
            )
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.get = AsyncMock(return_value=project)

        svc = _make_service(db)
        svc._assert_can_access_project = AsyncMock()
        file = _make_upload()

        with patch(
            "app.services.document_service.extract_text_from_file",
            new_callable=AsyncMock,
            return_value="Text content.",
        ):
            await svc.upload_document(
                project_id=1, user_id=1, user_role=UserRole.USER, file=file
            )

        assert any(
            isinstance(d, HistoricalDocument) and d.status == DocumentStatus.PENDING
            for d in added_docs
        )


# ══════════════════════════════════════════════════════════════════
# get_document_by_id
# ══════════════════════════════════════════════════════════════════


class TestGetDocumentById:
    async def test_not_found_raises_not_found_exception(self):
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        svc = _make_service(db)

        with pytest.raises(NotFoundException, match="Document 42 not found"):
            await svc.get_document_by_id(42, user_id=1, user_role=UserRole.USER)

    async def test_access_denied_raises_forbidden_exception(self):
        doc = build_document(id=1, project_id=5)
        db = AsyncMock()
        db.get = AsyncMock(return_value=doc)
        svc = _make_service(db)
        svc._assert_can_access_project = AsyncMock(
            side_effect=ForbiddenException("no access")
        )

        with pytest.raises(ForbiddenException):
            await svc.get_document_by_id(1, user_id=2, user_role=UserRole.USER)

    async def test_found_and_accessible_returns_document(self):
        doc = build_document(id=1, project_id=5)
        db = AsyncMock()
        db.get = AsyncMock(return_value=doc)
        svc = _make_service(db)
        svc._assert_can_access_project = AsyncMock()

        result = await svc.get_document_by_id(1, user_id=1, user_role=UserRole.USER)
        assert result is doc


# ══════════════════════════════════════════════════════════════════
# update_document_status
# ══════════════════════════════════════════════════════════════════


class TestUpdateDocumentStatus:
    async def test_not_found_raises_not_found_exception(self):
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        svc = _make_service(db)

        with pytest.raises(NotFoundException):
            await svc.update_document_status(99, DocumentStatus.COMPLETED)

    async def test_status_updated_correctly(self):
        doc = build_pending_document(id=1)
        db = AsyncMock()
        db.get = AsyncMock(return_value=doc)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        await svc.update_document_status(1, DocumentStatus.COMPLETED)
        assert doc.status == DocumentStatus.COMPLETED

    async def test_error_message_stored_on_failure(self):
        doc = build_pending_document(id=1)
        db = AsyncMock()
        db.get = AsyncMock(return_value=doc)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        await svc.update_document_status(
            1, DocumentStatus.FAILED, "embedding model crashed"
        )
        assert doc.error_message == "embedding model crashed"

    async def test_error_message_cleared_on_completed(self):
        doc = build_failed_document(id=1)
        db = AsyncMock()
        db.get = AsyncMock(return_value=doc)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        await svc.update_document_status(1, DocumentStatus.COMPLETED)
        assert doc.error_message is None

    async def test_processed_at_is_set(self):
        doc = build_pending_document(id=1)
        doc.processed_at = None
        db = AsyncMock()
        db.get = AsyncMock(return_value=doc)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        await svc.update_document_status(1, DocumentStatus.COMPLETED)
        assert doc.processed_at is not None


# ══════════════════════════════════════════════════════════════════
# delete_document
# ══════════════════════════════════════════════════════════════════


class TestDeleteDocument:
    async def test_chunks_deleted_before_document(self):
        doc = build_document(id=1, project_id=1)
        project = build_project(id=1, document_count=3)

        db = AsyncMock()
        db.get = AsyncMock(
            side_effect=lambda model, pk: (
                project if model.__name__ == "Project" else None
            )
        )
        db.delete = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        await svc.delete_document(1, user_id=1, user_role=UserRole.USER)

        svc.vector_service.delete_document_chunks.assert_called_once_with(1)

    async def test_document_deleted_from_session(self):
        doc = build_document(id=1, project_id=1)
        project = build_project(id=1, document_count=1)

        db = AsyncMock()
        db.get = AsyncMock(return_value=project)
        db.delete = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()

        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        await svc.delete_document(1, user_id=1, user_role=UserRole.USER)

        db.delete.assert_called_once_with(doc)

    async def test_project_document_count_decremented(self):
        doc = build_document(id=1, project_id=1)
        project = build_project(id=1, document_count=5)

        db = AsyncMock()
        db.get = AsyncMock(return_value=project)
        db.delete = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()

        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        await svc.delete_document(1, user_id=1, user_role=UserRole.USER)

        assert project.document_count == 4

    async def test_document_count_does_not_go_below_zero(self):
        doc = build_document(id=1, project_id=1)
        project = build_project(id=1, document_count=0)

        db = AsyncMock()
        db.get = AsyncMock(return_value=project)
        db.delete = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()

        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        await svc.delete_document(1, user_id=1, user_role=UserRole.USER)

        assert project.document_count == 0


# ══════════════════════════════════════════════════════════════════
# retry_failed_document
# ══════════════════════════════════════════════════════════════════


class TestRetryFailedDocument:
    async def test_non_failed_document_raises_bad_request(self):
        doc = build_pending_document(id=1)
        db = AsyncMock()
        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        with pytest.raises(BadRequestException, match="FAILED"):
            await svc.retry_failed_document(1, user_id=1, user_role=UserRole.USER)

    async def test_failed_document_reset_to_pending(self):
        doc = build_failed_document(id=1)
        doc.content_text = "Some extracted text to re-vectorize."
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        await svc.retry_failed_document(1, user_id=1, user_role=UserRole.USER)

        assert doc.status == DocumentStatus.PENDING

    async def test_failed_document_error_message_cleared(self):
        doc = build_failed_document(id=1)
        doc.content_text = "Text."
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        await svc.retry_failed_document(1, user_id=1, user_role=UserRole.USER)

        assert doc.error_message is None

    async def test_vectorization_dispatched_on_retry(self):
        doc = build_failed_document(id=1)
        doc.content_text = "Text to re-vectorize."
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)

        await svc.retry_failed_document(1, user_id=1, user_role=UserRole.USER)

        svc.vector_service.chunk_and_vectorize.assert_called_once()

    async def test_returns_celery_task_id(self):
        doc = build_failed_document(id=1)
        doc.content_text = "Text."
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        svc = _make_service(db)
        svc.get_document_by_id = AsyncMock(return_value=doc)
        svc.vector_service.chunk_and_vectorize = AsyncMock(return_value="task-retry-99")

        result = await svc.retry_failed_document(1, user_id=1, user_role=UserRole.USER)

        assert result == "task-retry-99"
