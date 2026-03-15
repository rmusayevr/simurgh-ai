"""
requeue_pending_documents.py
----------------------------
Re-dispatches Celery vectorization tasks for every document stuck in
PENDING or FAILED status.

Use this when:
  - Seed data was created before the Celery worker was running
  - A worker crash left documents stranded in PENDING
  - You want to force re-index all documents

Usage:
  docker compose exec backend python scripts/requeue_pending_documents.py

  # Dry run (shows what would be requeued without doing it):
  docker compose exec backend python scripts/requeue_pending_documents.py --dry-run

  # Requeue a specific document by ID:
  docker compose exec backend python scripts/requeue_pending_documents.py --id 5
"""

import asyncio
import argparse
import sys
import os

# Allow running from /app (Docker) or from backend/ directory locally
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.project import HistoricalDocument, DocumentStatus
from app.services.vector_service import VectorService


async def requeue(dry_run: bool = False, doc_id: int = None):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Build query
        query = select(HistoricalDocument).where(
            HistoricalDocument.status.in_(
                [DocumentStatus.PENDING, DocumentStatus.FAILED]
            )
        )
        if doc_id:
            query = select(HistoricalDocument).where(HistoricalDocument.id == doc_id)

        result = await session.exec(query)
        docs = result.all()

        if not docs:
            print("✓ No stuck documents found — nothing to requeue.")
            return

        print(f"Found {len(docs)} document(s) to requeue:\n")
        for doc in docs:
            print(
                f"  [{doc.id}] {doc.filename} — status={doc.status.value}, project_id={doc.project_id}"
            )

        if dry_run:
            print("\nDry run — no tasks dispatched. Remove --dry-run to proceed.")
            return

        print()
        vector_service = VectorService(session=session)
        success = 0
        failed = 0

        for doc in docs:
            if not doc.content_text:
                print(f"  ✗ [{doc.id}] {doc.filename} — no content_text, skipping")
                failed += 1
                continue
            try:
                # Reset status to PENDING before re-dispatching
                doc.status = DocumentStatus.PENDING
                doc.error_message = None
                doc.indexing_progress = 0
                session.add(doc)
                await session.commit()

                task_id = await vector_service.chunk_and_vectorize(
                    document_id=doc.id,
                    full_text=doc.content_text,
                )
                print(f"  ✓ [{doc.id}] {doc.filename} — task_id={task_id}")
                success += 1
            except Exception as e:
                print(f"  ✗ [{doc.id}] {doc.filename} — dispatch failed: {e}")
                failed += 1

        print(f"\nDone. {success} requeued, {failed} failed.")
        print("Watch worker logs: docker compose logs celery_worker --follow")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Requeue stuck documents for vectorization"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be requeued without doing it",
    )
    parser.add_argument(
        "--id", type=int, default=None, help="Requeue a specific document by ID"
    )
    args = parser.parse_args()

    asyncio.run(requeue(dry_run=args.dry_run, doc_id=args.id))
