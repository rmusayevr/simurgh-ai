"""
Admin - RAG verification and analytics endpoints.

GET /admin/rag/verification
GET /admin/analytics
"""

import structlog

from fastapi import APIRouter, Depends
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.models.project import HistoricalDocument
from app.models.proposal import Proposal
from app.models.stakeholder import Stakeholder
from app.models.chunk import DocumentChunk

logger = structlog.get_logger()
router = APIRouter()


@router.get("/rag/verification")
async def get_rag_verification(
    session: AsyncSession = Depends(get_session),
):
    """
    Verify RAG pipeline health.
    """
    doc_stmt = select(
        HistoricalDocument.filename,
        HistoricalDocument.status,
        HistoricalDocument.chunk_count,
        HistoricalDocument.upload_date,
    ).order_by(HistoricalDocument.upload_date.desc())

    doc_results = await session.exec(doc_stmt)
    documents = doc_results.all()

    chunk_count = (
        await session.exec(select(func.count()).select_from(DocumentChunk))
    ).one()

    return {
        "total_chunks": chunk_count,
        "total_documents": len(documents),
        "documents": [
            {
                "filename": doc.filename,
                "status": doc.status.value,
                "chunk_count": doc.chunk_count or 0,
                "created_at": doc.upload_date.isoformat(),
            }
            for doc in documents
        ],
    }


@router.get("/analytics")
async def get_system_analytics(
    session: AsyncSession = Depends(get_session),
):
    """
    Get aggregated system analytics.
    """
    try:
        proposal_count = (
            await session.exec(select(func.count()).select_from(Proposal))
        ).one()

        top_doc_stmt = (
            select(HistoricalDocument.filename)
            .order_by(HistoricalDocument.chunk_count.desc())
            .limit(1)
        )
        top_doc_result = await session.exec(top_doc_stmt)
        top_doc = top_doc_result.first() or "No documents"

        try:
            from sqlalchemy import case, literal

            sentiment_score = case(
                (Stakeholder.sentiment == "CHAMPION", literal(0)),
                (Stakeholder.sentiment == "SUPPORTIVE", literal(1)),
                (Stakeholder.sentiment == "NEUTRAL", literal(2)),
                (Stakeholder.sentiment == "CONCERNED", literal(3)),
                (Stakeholder.sentiment == "RESISTANT", literal(4)),
                (Stakeholder.sentiment == "BLOCKER", literal(5)),
                else_=literal(2),
            )
            avg_sentiment_stmt = select(func.avg(sentiment_score))
            avg_sentiment_result = await session.execute(avg_sentiment_stmt)
            avg_sentiment = avg_sentiment_result.scalar() or 0.0
        except Exception:
            avg_sentiment = 0.0

        return {
            "total_proposals": proposal_count,
            "top_referenced_document": top_doc,
            "avg_stakeholder_sentiment": round(float(avg_sentiment), 2),
            "system_health": "optimal",
        }

    except Exception as e:
        logger.error("analytics_failed", error=str(e))
        return {
            "total_proposals": 0,
            "top_referenced_document": "Error",
            "avg_stakeholder_sentiment": 0.0,
            "system_health": "error",
        }
