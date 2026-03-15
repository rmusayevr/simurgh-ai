"""Phase 7 — API: Document endpoints."""

import io
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.project import DocumentStatus
from datetime import datetime

BASE = "/api/v1/documents"
PID = 1
DOC_ID = 5


def _doc(id=DOC_ID, project_id=PID):
    d = MagicMock()

    d.id = id
    d.project_id = project_id
    d.filename = "test.pdf"
    d.file_size_bytes = 1234
    d.mime_type = "application/pdf"
    d.status = DocumentStatus.PENDING
    d.chunk_count = 0
    d.character_count = 0
    d.upload_date = datetime.now()
    d.processed_at = None
    d.uploaded_by_id = 1

    return d


class TestUploadDocument:
    async def test_upload_valid_pdf_returns_201(self, user_client):
        from app.services.document_service import DocumentService

        with patch.object(
            DocumentService, "upload_document", new=AsyncMock(return_value=_doc())
        ):
            resp = await user_client.post(
                f"{BASE}/projects/{PID}/documents",
                files={
                    "file": (
                        "test.pdf",
                        io.BytesIO(b"%PDF-1.4 content"),
                        "application/pdf",
                    )
                },
            )
        assert resp.status_code == 201

    async def test_upload_invalid_extension_returns_400_or_422(self, user_client):
        from app.services.document_service import DocumentService
        from app.core.exceptions import BadRequestException

        with patch.object(
            DocumentService,
            "upload_document",
            new=AsyncMock(side_effect=BadRequestException("Unsupported file type")),
        ):
            resp = await user_client.post(
                f"{BASE}/projects/{PID}/documents",
                files={
                    "file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")
                },
            )
        assert resp.status_code in (400, 422)

    async def test_upload_requires_auth(self, client):
        resp = await client.post(
            f"{BASE}/projects/{PID}/documents",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert resp.status_code == 401


class TestDeleteDocument:
    async def test_delete_returns_204(self, user_client):
        from app.services.document_service import DocumentService

        with patch.object(
            DocumentService, "delete_document", new=AsyncMock(return_value=None)
        ):
            resp = await user_client.delete(f"{BASE}/{DOC_ID}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_returns_404(self, user_client):
        from app.services.document_service import DocumentService
        from app.core.exceptions import NotFoundException

        with patch.object(
            DocumentService,
            "delete_document",
            new=AsyncMock(side_effect=NotFoundException("nf")),
        ):
            resp = await user_client.delete(f"{BASE}/9999")
        assert resp.status_code == 404

    async def test_delete_requires_auth(self, client):
        assert (await client.delete(f"{BASE}/{DOC_ID}")).status_code == 401
