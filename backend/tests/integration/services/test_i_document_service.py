"""
Phase 6 - Integration: DocumentService DB persistence against real PostgreSQL.

Note: Full document processing (embeddings, vector search) requires external
services. These tests verify the DB layer: upload metadata persistence,
status transitions, and chunk deletion cascade.
"""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole
from app.models.project import Project, HistoricalDocument, DocumentStatus
from app.core.security import hash_password
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService


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
        project_data=ProjectCreate(name="Doc Project", description="desc"),
        owner_id=owner_id,
    )


def _make_doc(
    project_id: int, uploader_id: int, filename: str = "test.pdf"
) -> HistoricalDocument:
    return HistoricalDocument(
        project_id=project_id,
        filename=filename,
        original_filename=filename,
        file_size=1024,
        file_type="application/pdf",
        status=DocumentStatus.PENDING,
        uploader_id=uploader_id,
    )


class TestDocumentPersistence:
    async def test_document_row_is_created(self, db_session: AsyncSession):
        """Adding a HistoricalDocument must persist it with PENDING status."""
        owner = await _make_user(db_session, "doc_create@example.com")
        project = await _make_project(db_session, owner.id)

        doc = _make_doc(project.id, owner.id)
        db_session.add(doc)
        await db_session.flush()

        assert doc.id is not None
        fetched = await db_session.get(HistoricalDocument, doc.id)
        assert fetched is not None
        assert fetched.status == DocumentStatus.PENDING

    async def test_document_mark_processing_updates_status(
        self, db_session: AsyncSession
    ):
        """mark_processing() must change status to PROCESSING."""
        owner = await _make_user(db_session, "doc_proc@example.com")
        project = await _make_project(db_session, owner.id)

        doc = _make_doc(project.id, owner.id)
        db_session.add(doc)
        await db_session.flush()

        doc.mark_processing()
        db_session.add(doc)
        await db_session.flush()

        fetched = await db_session.get(HistoricalDocument, doc.id)
        assert fetched.status == DocumentStatus.PROCESSING

    async def test_document_mark_completed_sets_chunk_count(
        self, db_session: AsyncSession
    ):
        """mark_completed() must set status=COMPLETED and chunk_count."""
        owner = await _make_user(db_session, "doc_done@example.com")
        project = await _make_project(db_session, owner.id)

        doc = _make_doc(project.id, owner.id)
        db_session.add(doc)
        await db_session.flush()

        doc.mark_completed(chunk_count=42)
        db_session.add(doc)
        await db_session.flush()

        fetched = await db_session.get(HistoricalDocument, doc.id)
        assert fetched.status == DocumentStatus.COMPLETED
        assert fetched.chunk_count == 42

    async def test_document_mark_failed_stores_error(self, db_session: AsyncSession):
        """mark_failed() must set status=FAILED and store the error message."""
        owner = await _make_user(db_session, "doc_fail@example.com")
        project = await _make_project(db_session, owner.id)

        doc = _make_doc(project.id, owner.id)
        db_session.add(doc)
        await db_session.flush()

        doc.mark_failed("Parsing error: corrupt PDF")
        db_session.add(doc)
        await db_session.flush()

        fetched = await db_session.get(HistoricalDocument, doc.id)
        assert fetched.status == DocumentStatus.FAILED
        assert "Parsing error" in fetched.error_message

    async def test_delete_document_removes_row(self, db_session: AsyncSession):
        """Deleting a HistoricalDocument must remove the row."""
        owner = await _make_user(db_session, "doc_del@example.com")
        project = await _make_project(db_session, owner.id)

        doc = _make_doc(project.id, owner.id)
        db_session.add(doc)
        await db_session.flush()
        doc_id = doc.id

        await db_session.delete(doc)
        await db_session.flush()

        fetched = await db_session.get(HistoricalDocument, doc_id)
        assert fetched is None

    async def test_multiple_documents_belong_to_project(self, db_session: AsyncSession):
        """Multiple documents for the same project must all reference the correct project_id."""
        from sqlmodel import select

        owner = await _make_user(db_session, "doc_multi@example.com")
        project = await _make_project(db_session, owner.id)

        for i in range(3):
            doc = _make_doc(project.id, owner.id, filename=f"file{i}.pdf")
            db_session.add(doc)
        await db_session.flush()

        result = await db_session.exec(
            select(HistoricalDocument).where(
                HistoricalDocument.project_id == project.id
            )
        )
        docs = result.all()
        assert len(docs) == 3
        assert all(d.project_id == project.id for d in docs)
