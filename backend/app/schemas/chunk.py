"""
Document chunk schemas for RAG pipeline.

These schemas serve the vector search and document processing endpoints.
Chunks are created internally by the RAG pipeline (not directly by users),
so there are no Create schemas — only Read and search-related schemas.

Pipeline flow reflected here:
    1. Document uploaded → HistoricalDocumentRead (project.py)
    2. Processing triggered → ChunkProcessingStatus
    3. Chunks created → DocumentChunkRead
    4. Search query → ChunkSearchRequest → ChunkSearchResult
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.models.project import DocumentStatus


# ==================== Chunk Read Schemas ====================


class DocumentChunkRead(BaseModel):
    """
    Full chunk record including content and indexing status.
    Used for debugging, admin inspection, and RAG pipeline monitoring.
    """

    id: int
    document_id: int
    chunk_index: int
    content: str
    content_length: int
    page_number: Optional[int]
    section_title: Optional[str]
    start_char: Optional[int]
    end_char: Optional[int]

    # Indexing status flags (derived from model properties)
    has_embedding: bool
    has_search_vector: bool
    is_indexed: bool
    word_count: int

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkMinimalRead(BaseModel):
    """
    Lightweight chunk summary for embedding in document detail responses.
    Excludes content and vector fields — only structural metadata.
    """

    id: int
    chunk_index: int
    content_length: int
    word_count: int
    page_number: Optional[int]
    section_title: Optional[str]
    is_indexed: bool

    model_config = ConfigDict(from_attributes=True)


# ==================== Processing Status ====================


class ChunkProcessingStatus(BaseModel):
    """
    Processing status summary for a document's chunks.

    Returned by the document processing status endpoint to let
    the frontend show RAG pipeline progress.
    """

    document_id: int
    document_status: DocumentStatus
    total_chunks: int
    indexed_chunks: int  # chunks with both embedding + search_vector
    pending_chunks: int  # chunks missing embedding or search_vector
    failed_chunks: int  # chunks with no embedding at all

    model_config = ConfigDict(from_attributes=True)

    @property
    def indexing_progress(self) -> float:
        """Percentage of chunks fully indexed (0.0-100.0)."""
        if self.total_chunks == 0:
            return 0.0
        return round((self.indexed_chunks / self.total_chunks) * 100, 1)

    @property
    def is_ready_for_rag(self) -> bool:
        """Whether document is fully indexed and ready for semantic search."""
        return (
            self.document_status == DocumentStatus.COMPLETED
            and self.total_chunks > 0
            and self.indexed_chunks == self.total_chunks
        )


# ==================== Search Schemas ====================


class ChunkSearchRequest(BaseModel):
    """
    Request schema for semantic or hybrid chunk search.

    Used internally by the debate service and proposal service
    to retrieve relevant context from project documents during
    AI generation (RAG pipeline step 6).
    """

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Search query for semantic similarity or full-text search",
    )

    document_ids: Optional[List[int]] = Field(
        default=None,
        description="Limit search to specific document IDs (null = search all)",
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of most relevant chunks to return",
    )

    min_content_length: Optional[int] = Field(
        default=50,
        ge=0,
        description="Minimum chunk character length to include in results",
    )

    search_mode: str = Field(
        default="hybrid",
        description="Search mode: 'semantic' (pgvector), 'fulltext' (tsvector), or 'hybrid'",
    )

    @property
    def is_hybrid(self) -> bool:
        return self.search_mode == "hybrid"

    @property
    def is_semantic(self) -> bool:
        return self.search_mode == "semantic"

    @property
    def is_fulltext(self) -> bool:
        return self.search_mode == "fulltext"


class ChunkSearchResult(BaseModel):
    """
    Single chunk returned from a similarity search.
    Includes relevance score and source provenance for RAG context building.
    """

    chunk_id: int
    document_id: int
    chunk_index: int
    content: str
    content_length: int
    page_number: Optional[int]
    section_title: Optional[str]
    similarity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Cosine similarity score (1.0 = most similar)",
    )
    search_mode_used: str = Field(
        description="Which search mode produced this result (semantic/fulltext/hybrid)",
    )

    model_config = ConfigDict(from_attributes=True)


class ChunkSearchResponse(BaseModel):
    """
    Full response from a chunk search query.
    Wraps results with query metadata for RAG context tracing.
    """

    query: str
    search_mode: str
    total_results: int
    results: List[ChunkSearchResult] = Field(default_factory=list)
    document_ids_searched: List[int] = Field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return len(self.results) > 0

    @property
    def top_result(self) -> Optional[ChunkSearchResult]:
        """Most relevant chunk — highest similarity score."""
        if not self.results:
            return None
        return self.results[0]

    def to_context_string(self) -> str:
        """
        Format results as a single context string for injection into AI prompts.

        Used by debate service and proposal service to build
        the RAG context block passed to Claude.

        Returns:
            str: Formatted context with source attribution per chunk
        """
        if not self.results:
            return "No relevant context found."

        parts = []
        for i, chunk in enumerate(self.results, 1):
            source = f"[Source: Document {chunk.document_id}"
            if chunk.page_number:
                source += f", Page {chunk.page_number}"
            if chunk.section_title:
                source += f", Section: '{chunk.section_title}'"
            source += "]"

            parts.append(f"--- Context {i} {source} ---\n{chunk.content}")

        return "\n\n".join(parts)
