"""
Vector service for document chunking, embedding, and semantic search.

Handles RAG pipeline:
    - Text chunking with configurable overlap
    - Embedding generation (FastEmbed)
    - Vector storage (pgvector)
    - Hybrid search (semantic + keyword via RRF)
    - Background processing via Celery

Chunking strategy:
    - Fixed-size chunks with overlap to preserve context
    - Configured via settings.CHUNK_SIZE and settings.CHUNK_OVERLAP
    - Progress tracking for frontend status updates

Search strategy:
    - Hybrid: Reciprocal Rank Fusion of semantic (pgvector) + keyword (FTS)
    - Fallback: Pure semantic search if hybrid fails
    - Configurable weights for semantic vs keyword
"""

import structlog
from typing import List, Dict, Optional
from fastembed import TextEmbedding
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.project import HistoricalDocument, DocumentStatus
from app.core.config import settings
from app.core.celery_app import celery_app
from app.db.session import get_sync_session

logger = structlog.get_logger()

_model: Optional[TextEmbedding] = None


def get_embedding_model() -> TextEmbedding:
    """
    Get or initialize the FastEmbed model.

    Lazily loads the model on first use and caches for performance.
    Uses the model specified in settings.EMBEDDING_MODEL.

    Asserts on first load that the model produces exactly
    settings.EMBEDDING_DIMENSIONS vectors, so a misconfigured
    EMBEDDING_DIMENSIONS value is caught immediately rather than
    silently storing wrong-sized vectors in pgvector.

    Returns:
        TextEmbedding: Initialized embedding model
    """
    global _model
    if _model is None:
        logger.info(
            "loading_embedding_model",
            model=settings.EMBEDDING_MODEL,
            expected_dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        _model = TextEmbedding(model_name=settings.EMBEDDING_MODEL)

        _probe = list(_model.embed(["dimension check"]))[0]
        actual_dims = len(_probe)
        if actual_dims != settings.EMBEDDING_DIMENSIONS:
            _model = None
            raise RuntimeError(
                f"Embedding model '{settings.EMBEDDING_MODEL}' produced "
                f"{actual_dims}-dim vectors but EMBEDDING_DIMENSIONS="
                f"{settings.EMBEDDING_DIMENSIONS}. Update config.py or "
                f"create an Alembic migration to resize the vector column."
            )

        logger.info(
            "embedding_model_loaded",
            model=settings.EMBEDDING_MODEL,
            dimensions=actual_dims,
        )
    return _model


# ==================== Chunking Utilities ====================


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Split text into overlapping chunks.

    Overlap prevents context cutoff at chunk boundaries, improving
    RAG retrieval quality for queries that span chunk edges.

    Args:
        text: Full text to chunk
        chunk_size: Target chunk size in characters
        overlap: Number of overlapping characters between chunks

    Returns:
        List[str]: Text chunks with overlap

    Example:
        >>> chunks = chunk_text("ABCDEFGHIJ", chunk_size=4, overlap=2)
        >>> # Returns: ["ABCD", "CDEF", "EFGH", "GHIJ"]
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]

        if chunk.strip():  # Skip empty chunks
            chunks.append(chunk)

        # Move start position forward, accounting for overlap
        start = end - overlap
        if start >= text_length:
            break

    return chunks


# ==================== Celery Task ====================


@celery_app.task(
    name="process_document_embeddings", bind=True, max_retries=3, queue="vectorization"
)
def process_document_embeddings_task(self, document_id: int, full_text: str):
    """
    Background task to vectorize document chunks.

    Flow:
        1. Mark document as PROCESSING
        2. Chunk text with overlap
        3. Generate embeddings for all chunks
        4. Save DocumentChunk records with vectors
        5. Update HistoricalDocument status and chunk_count
        6. On failure: Mark document as FAILED and retry with backoff

    Args:
        document_id: HistoricalDocument primary key
        full_text: Full extracted text to vectorize

    Raises:
        Retry: On any failure (max 3 retries with exponential backoff)
    """
    log = logger.bind(
        task="vectorize_doc",
        document_id=document_id,
        text_length=len(full_text),
    )
    log.info("task_started")

    session = next(get_sync_session())

    try:
        # Mark document as processing
        doc = session.get(HistoricalDocument, document_id)
        if not doc:
            log.error("document_not_found")
            return {"error": "Document not found"}

        doc.status = DocumentStatus.PROCESSING
        doc.indexing_progress = 0  # Reset progress
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # Chunk text with overlap
        chunks = chunk_text(
            text=full_text,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )

        if not chunks:
            log.warning("no_chunks_generated", text_length=len(full_text))
            doc.status = DocumentStatus.FAILED
            doc.error_message = "No valid chunks generated from text"
            session.add(doc)
            session.commit()
            return {"error": "No chunks generated"}

        log.info("chunks_created", count=len(chunks))

        # Generate embeddings
        model = get_embedding_model()
        embeddings_generator = model.embed(chunks)
        embeddings_list = list(embeddings_generator)

        log.info("embeddings_generated", count=len(embeddings_list))

        # Create DocumentChunk records
        new_chunks = []
        for i, (text_chunk, vector) in enumerate(zip(chunks, embeddings_list)):
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                content=text_chunk,
                embedding=vector.tolist(),
                # search_vector populated automatically by DB trigger on INSERT
            )
            new_chunks.append(chunk)

            # Update progress every 10 chunks
            if i % 10 == 0:
                progress = int((i / len(chunks)) * 100)
                doc.indexing_progress = progress
                session.add(doc)
                session.commit()

        session.add_all(new_chunks)

        # Mark document as completed
        doc.status = DocumentStatus.COMPLETED
        doc.chunk_count = len(new_chunks)
        doc.indexing_progress = 100
        doc.error_message = None  # Clear any previous errors
        session.add(doc)

        session.commit()
        log.info("task_success", chunks_saved=len(new_chunks))

        return {"status": "success", "chunks": len(new_chunks)}

    except Exception as exc:
        session.rollback()
        log.exception("task_failed", error=str(exc))

        # Mark document as failed
        try:
            doc = session.get(HistoricalDocument, document_id)
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = f"Vectorization failed: {str(exc)}"
                session.add(doc)
                session.commit()
        except Exception as update_error:
            log.error("failed_to_update_status", error=str(update_error))

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))

    finally:
        session.close()


# ==================== Vector Service ====================


class VectorService:
    """
    Service for document chunking, embedding, and semantic search.

    Provides:
        - Async methods for chunk retrieval and search
        - Celery task dispatching for background vectorization
        - Hybrid search (semantic + keyword) with RRF
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Vectorization ====================

    async def chunk_and_vectorize(self, document_id: int, full_text: str) -> str:
        """
        Dispatch document vectorization to Celery worker.

        Args:
            document_id: HistoricalDocument primary key
            full_text: Full extracted text to vectorize

        Returns:
            str: Celery task ID for status tracking
        """
        task = process_document_embeddings_task.delay(document_id, full_text)

        logger.info(
            "vectorization_enqueued",
            document_id=document_id,
            celery_task_id=task.id,
        )
        return task.id

    # ==================== Chunk Management ====================

    async def get_document_chunks(
        self, document_id: int, limit: Optional[int] = None
    ) -> List[DocumentChunk]:
        """
        Get all chunks for a document, ordered by chunk_index.

        Args:
            document_id: HistoricalDocument primary key
            limit: Optional max chunks to return

        Returns:
            List[DocumentChunk]: Ordered chunks
        """
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )

        if limit:
            query = query.limit(limit)

        result = await self.session.exec(query)
        return result.all()

    async def delete_document_chunks(self, document_id: int) -> int:
        """
        Delete all chunks for a document.

        Used when re-processing a document or cleaning up after deletion.

        Args:
            document_id: HistoricalDocument primary key

        Returns:
            int: Number of chunks deleted
        """
        result = await self.session.exec(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = result.all()

        for chunk in chunks:
            await self.session.delete(chunk)

        await self.session.commit()

        logger.info("chunks_deleted", document_id=document_id, count=len(chunks))
        return len(chunks)

    # ==================== Search ====================

    async def search_similar(
        self, query: str, limit: int = 5, document_ids: Optional[List[int]] = None
    ) -> List[DocumentChunk]:
        """
        Semantic search using vector similarity.

        Wrapper that defaults to hybrid search for better accuracy.
        Use `semantic_search_only()` for pure vector search.

        Args:
            query: Search query text
            limit: Max results to return
            document_ids: Optional list to restrict search scope

        Returns:
            List[DocumentChunk]: Ranked results
        """
        return await self.hybrid_search(
            query=query, limit=limit, document_ids=document_ids
        )

    async def semantic_search_only(
        self,
        query: str,
        limit: int = 5,
        document_ids: Optional[List[int]] = None,
    ) -> List[DocumentChunk]:
        """
        Pure semantic search using pgvector cosine similarity.

        Args:
            query: Search query text
            limit: Max results to return
            document_ids: Optional list to restrict search scope

        Returns:
            List[DocumentChunk]: Ranked by cosine similarity
        """
        try:
            model = get_embedding_model()
            query_vector = list(model.embed([query]))[0].tolist()

            stmt = select(DocumentChunk).order_by(
                DocumentChunk.embedding.cosine_distance(query_vector)
            )

            if document_ids:
                stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

            stmt = stmt.limit(limit)

            result = await self.session.exec(stmt)
            return result.all()

        except Exception as e:
            logger.error(
                "semantic_search_failed",
                error=str(e),
                query=query,
            )
            return []

    async def keyword_search_only(
        self,
        query: str,
        limit: int = 5,
        document_ids: Optional[List[int]] = None,
    ) -> List[DocumentChunk]:
        """
        Pure keyword search using PostgreSQL full-text search.

        Args:
            query: Search query text
            limit: Max results to return
            document_ids: Optional list to restrict search scope

        Returns:
            List[DocumentChunk]: Ranked by ts_rank
        """
        try:
            stmt = (
                select(DocumentChunk)
                .where(text("search_vector @@ plainto_tsquery('english', :q)"))
                .order_by(
                    text("ts_rank(search_vector, plainto_tsquery('english', :q)) DESC")
                )
            ).params(q=query)

            if document_ids:
                stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

            stmt = stmt.limit(limit)

            result = await self.session.exec(stmt)
            return result.all()

        except Exception as e:
            logger.error(
                "keyword_search_failed",
                error=str(e),
                query=query,
            )
            return []

    async def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        document_ids: Optional[List[int]] = None,
    ) -> List[DocumentChunk]:
        """
        Hybrid search combining semantic and keyword search using RRF.

        Reciprocal Rank Fusion (RRF) is a rank aggregation method that
        combines rankings from multiple retrieval systems. It's more
        robust than score-based fusion and doesn't require normalization.

        Formula: score = weight * (1 / (k + rank))
        where k=60 is a constant that prevents very top ranks from
        dominating the score.

        Args:
            query: Search query text
            limit: Max final results to return
            semantic_weight: Weight for vector similarity (default 0.7)
            keyword_weight: Weight for keyword relevance (default 0.3)
            document_ids: Optional list to restrict search scope

        Returns:
            List[DocumentChunk]: Fused and re-ranked results

        References:
            - Cormack et al., "Reciprocal Rank Fusion outperforms Condorcet
              and individual Rank Learning Methods" (SIGIR 2009)
        """
        try:
            # Generate query embedding
            model = get_embedding_model()
            query_vector = list(model.embed([query]))[0].tolist()

            # Fetch more candidates for re-ranking
            candidate_limit = limit * 2

            # Run semantic search
            semantic_stmt = select(DocumentChunk).order_by(
                DocumentChunk.embedding.cosine_distance(query_vector)
            )

            if document_ids:
                semantic_stmt = semantic_stmt.where(
                    DocumentChunk.document_id.in_(document_ids)
                )

            semantic_stmt = semantic_stmt.limit(candidate_limit)
            semantic_results = await self.session.exec(semantic_stmt)
            semantic_chunks = semantic_results.all()

            # Run keyword search
            keyword_stmt = (
                select(DocumentChunk)
                .where(text("search_vector @@ plainto_tsquery('english', :q)"))
                .order_by(
                    text("ts_rank(search_vector, plainto_tsquery('english', :q)) DESC")
                )
            ).params(q=query)

            if document_ids:
                keyword_stmt = keyword_stmt.where(
                    DocumentChunk.document_id.in_(document_ids)
                )

            keyword_stmt = keyword_stmt.limit(candidate_limit)
            keyword_results = await self.session.exec(keyword_stmt)
            keyword_chunks = keyword_results.all()

            # Reciprocal Rank Fusion (RRF)
            rrf_scores: Dict[int, float] = {}
            k_constant = 60  # Standard RRF constant

            # Build chunk map for efficient lookup
            all_chunks_map = {c.id: c for c in semantic_chunks + keyword_chunks}

            # Score semantic results
            for rank, chunk in enumerate(semantic_chunks):
                if chunk.id is not None:
                    rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + (
                        semantic_weight / (k_constant + rank + 1)
                    )

            # Score keyword results
            for rank, chunk in enumerate(keyword_chunks):
                if chunk.id is not None:
                    rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + (
                        keyword_weight / (k_constant + rank + 1)
                    )

            # Sort by RRF score and return top results
            sorted_ids = sorted(
                rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True
            )

            top_ids = sorted_ids[:limit]
            top_chunks = [all_chunks_map[chunk_id] for chunk_id in top_ids]

            logger.info(
                "hybrid_search_completed",
                query=query,
                semantic_candidates=len(semantic_chunks),
                keyword_candidates=len(keyword_chunks),
                results=len(top_chunks),
            )

            return top_chunks

        except Exception as e:
            logger.error("hybrid_search_failed", error=str(e), query=query)

            # Fallback to pure semantic search
            logger.info("falling_back_to_semantic_search")
            return await self.semantic_search_only(
                query=query, limit=limit, document_ids=document_ids
            )
