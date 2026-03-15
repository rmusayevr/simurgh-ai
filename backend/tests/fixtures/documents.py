"""
Document factory fixtures.

Provides in-memory HistoricalDocument instances and sample binary content
for document service and API upload tests.

Also includes DocumentChunk builders for RAG/vector search tests.
"""

from __future__ import annotations

import io
import pytest
from datetime import datetime, timezone

from app.models.project import HistoricalDocument, DocumentStatus


# ── Sample file content ────────────────────────────────────────────────────────

_SAMPLE_PDF_CONTENT = b"%PDF-1.4 sample content for testing"
_SAMPLE_DOCX_HEADER = b"PK\x03\x04"  # DOCX/ZIP magic bytes
_SAMPLE_TXT_CONTENT = b"This is a plain text architecture document for testing."
_SAMPLE_MD_CONTENT = b"# Architecture Decision Record\n\nThis ADR covers the migration."


def sample_pdf_bytes() -> bytes:
    """Return minimal fake PDF bytes (not a valid PDF, but passes extension checks)."""
    return _SAMPLE_PDF_CONTENT


def sample_docx_bytes() -> bytes:
    """Return minimal fake DOCX bytes (ZIP magic header)."""
    return _SAMPLE_DOCX_HEADER + b"\x00" * 100


def sample_txt_bytes() -> bytes:
    """Return plain text bytes."""
    return _SAMPLE_TXT_CONTENT


def sample_md_bytes() -> bytes:
    """Return Markdown bytes."""
    return _SAMPLE_MD_CONTENT


def make_upload_file(
    filename: str = "spec.pdf",
    content: bytes | None = None,
    content_type: str = "application/pdf",
):
    """
    Build a dict that mimics a FastAPI UploadFile for testing document uploads.

    In unit tests, pass this dict to service methods.
    For API tests, use httpx's `files=` parameter instead.

    Args:
        filename:     Original filename (extension determines type validation)
        content:      Raw bytes (defaults to sample PDF bytes)
        content_type: MIME type

    Returns:
        dict: {"filename": str, "content": bytes, "content_type": str, "size": int}
    """
    data = content or _SAMPLE_PDF_CONTENT
    return {
        "filename": filename,
        "content": data,
        "content_type": content_type,
        "size": len(data),
        "file": io.BytesIO(data),
    }


# ── Document model factories ───────────────────────────────────────────────────


def build_document(
    id: int = 1,
    filename: str = "architecture_spec.pdf",
    project_id: int = 1,
    uploaded_by_id: int | None = 1,
    status: DocumentStatus = DocumentStatus.COMPLETED,
    content_text: str | None = (
        "This document describes the microservices migration strategy. "
        "The system currently uses a monolithic architecture with PostgreSQL. "
        "The proposed migration involves splitting into 6 bounded contexts."
    ),
    file_size_bytes: int = 204_800,  # 200 KB
    mime_type: str = "application/pdf",
    chunk_count: int = 3,
    error_message: str | None = None,
) -> HistoricalDocument:
    """
    Build an in-memory HistoricalDocument.

    Args:
        id:               PK
        filename:         Original filename
        project_id:       FK to Project
        uploaded_by_id:   FK to User who uploaded
        status:           Processing status
        content_text:     Extracted text (None if not yet processed)
        file_size_bytes:  File size
        mime_type:        MIME type
        chunk_count:      Number of RAG chunks created
        error_message:    Error if processing failed

    Returns:
        HistoricalDocument: Unsaved instance
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return HistoricalDocument(
        id=id,
        filename=filename,
        project_id=project_id,
        uploaded_by_id=uploaded_by_id,
        status=status,
        content_text=content_text,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        chunk_count=chunk_count,
        character_count=len(content_text) if content_text else 0,
        upload_date=now,
        processed_at=now if status == DocumentStatus.COMPLETED else None,
        error_message=error_message,
    )


def build_pending_document(id: int = 1, project_id: int = 1) -> HistoricalDocument:
    """Document just uploaded — not yet processed."""
    return build_document(
        id=id,
        project_id=project_id,
        status=DocumentStatus.PENDING,
        content_text=None,
        chunk_count=0,
    )


def build_processing_document(id: int = 1, project_id: int = 1) -> HistoricalDocument:
    """Document currently being chunked and vectorised."""
    return build_document(
        id=id,
        project_id=project_id,
        status=DocumentStatus.PROCESSING,
        content_text=None,
        chunk_count=0,
    )


def build_failed_document(id: int = 1, project_id: int = 1) -> HistoricalDocument:
    """Document whose processing failed."""
    return build_document(
        id=id,
        project_id=project_id,
        status=DocumentStatus.FAILED,
        content_text=None,
        chunk_count=0,
        error_message="Failed to extract text: corrupted PDF structure",
    )


def build_txt_document(id: int = 1, project_id: int = 1) -> HistoricalDocument:
    """Plain-text document."""
    return build_document(
        id=id,
        filename="notes.txt",
        project_id=project_id,
        mime_type="text/plain",
        file_size_bytes=512,
        content_text=_SAMPLE_TXT_CONTENT.decode(),
        chunk_count=1,
    )


def build_oversized_document(id: int = 1, project_id: int = 1) -> HistoricalDocument:
    """Document that exceeds the MAX_UPLOAD_SIZE_MB limit."""
    max_bytes = 51 * 1024 * 1024  # 51 MB (default limit is 50 MB)
    return build_document(
        id=id,
        project_id=project_id,
        file_size_bytes=max_bytes,
    )


# ── pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def test_document() -> HistoricalDocument:
    """Standard completed PDF document."""
    return build_document()


@pytest.fixture
def test_pending_document() -> HistoricalDocument:
    """Document freshly uploaded, awaiting processing."""
    return build_pending_document()


@pytest.fixture
def test_failed_document() -> HistoricalDocument:
    """Document that failed processing."""
    return build_failed_document()


@pytest.fixture
def test_txt_document() -> HistoricalDocument:
    """Plain text document (allowed extension)."""
    return build_txt_document()


@pytest.fixture
def sample_pdf_upload() -> dict:
    """Upload file dict for a valid PDF."""
    return make_upload_file("architecture.pdf", sample_pdf_bytes(), "application/pdf")


@pytest.fixture
def sample_docx_upload() -> dict:
    """Upload file dict for a valid DOCX."""
    return make_upload_file(
        "spec.docx",
        sample_docx_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@pytest.fixture
def sample_txt_upload() -> dict:
    """Upload file dict for a plain text file."""
    return make_upload_file("notes.txt", sample_txt_bytes(), "text/plain")


@pytest.fixture
def invalid_exe_upload() -> dict:
    """Upload file dict for a .exe — should be rejected."""
    return make_upload_file("malware.exe", b"MZ\x90\x00", "application/octet-stream")


@pytest.fixture
def oversized_upload() -> dict:
    """Upload file dict that exceeds the size limit."""
    big_content = b"x" * (51 * 1024 * 1024)  # 51 MB
    return make_upload_file("huge.pdf", big_content, "application/pdf")


@pytest.fixture
def make_document():
    """
    Parameterizable document factory.

    Usage:
        def test_custom(make_document):
            doc = make_document(filename="other.docx", chunk_count=10)
    """
    return build_document
