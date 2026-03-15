"""
Document chunk model for RAG (Retrieval-Augmented Generation) pipeline.

When a document is uploaded, it is split into overlapping chunks and
each chunk is vectorized for semantic similarity search.

This enables AI agents to retrieve relevant context during debates
and proposal generation.

Pipeline:
    1. Upload document (HistoricalDocument)
    2. Extract text (parsers.py)
    3. Split into chunks (vector_service.py)
    4. Generate embeddings (OpenAI/HuggingFace)
    5. Store chunks with vectors here
    6. Retrieve similar chunks during AI generation (RAG)

Search Modes:
    - Semantic search: Uses pgvector cosine similarity
    - Full-text search: Uses PostgreSQL TSVECTOR
    - Hybrid: Combines both for best results
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, Column, Text
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector

if TYPE_CHECKING:
    from app.models.project import HistoricalDocument


class DocumentChunk(SQLModel, table=True):
    """
    Text chunk from a processed document with vector embedding.

    Each chunk represents a semantically meaningful piece of text
    that can be retrieved via similarity search during AI generation.

    Attributes:
        id: Primary key
        document_id: FK to parent document
        chunk_index: Position within document (0-indexed)
        content: Raw text content of this chunk
        content_length: Character count for filtering
        embedding: Vector embedding for semantic search (384 dims)
        search_vector: TSVECTOR for full-text search
        page_number: Source page in document (if applicable)
        section_title: Section heading (if extractable)
        created_at: Chunk creation timestamp
    """

    __tablename__ = "document_chunks"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Chunk ID",
    )

    # ==================== Foreign Keys ====================

    document_id: int = Field(
        foreign_key="historical_documents.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        description="Parent document ID",
    )

    # ==================== Content ====================

    content: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Raw text content of this chunk",
    )

    content_length: int = Field(
        default=0,
        description="Character count (for filtering short/long chunks)",
    )

    chunk_index: int = Field(
        nullable=False,
        ge=0,
        description="Position within document (0-indexed)",
    )

    # ==================== Source Location ====================

    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Source page number in document (if applicable)",
    )

    section_title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Section heading this chunk belongs to (if extractable)",
    )

    start_char: Optional[int] = Field(
        default=None,
        ge=0,
        description="Start character position in full document text",
    )

    end_char: Optional[int] = Field(
        default=None,
        ge=0,
        description="End character position in full document text",
    )

    # ==================== Vector Search ====================

    embedding: Optional[List[float]] = Field(
        default=None,
        sa_column=Column(
            Vector(384),
            nullable=True,
        ),
        description="Vector embedding for semantic similarity search (384 dims)",
    )

    # ==================== Full-Text Search ====================

    search_vector: Optional[str] = Field(
        default=None,
        sa_column=Column(
            "search_vector",
            TSVECTOR,
            nullable=True,
        ),
        description="PostgreSQL TSVECTOR for full-text search",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        description="Chunk creation timestamp (UTC)",
    )

    # ==================== Relationships ====================

    document: "HistoricalDocument" = Relationship(
        back_populates="chunks",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # ==================== Indexes ====================

    __table_args__ = (
        # Standard indexes
        Index("idx_chunk_document_index", "document_id", "chunk_index"),
        Index("idx_chunk_document_page", "document_id", "page_number"),
        # Full-text search index (GIN for TSVECTOR)
        Index(
            "idx_chunk_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        # Vector similarity index (HNSW for fast approximate search)
        Index(
            "idx_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    # ==================== Helper Methods ====================

    @property
    def has_embedding(self) -> bool:
        """Check if chunk has been vectorized."""
        return self.embedding is not None and len(self.embedding) > 0

    @property
    def has_search_vector(self) -> bool:
        """Check if chunk has full-text search vector."""
        return self.search_vector is not None

    @property
    def is_indexed(self) -> bool:
        """Check if chunk is fully indexed (both vector and FTS)."""
        return self.has_embedding and self.has_search_vector

    @property
    def word_count(self) -> int:
        """Get approximate word count."""
        return len(self.content.split())

    def set_content(self, text: str) -> None:
        """
        Set chunk content and auto-calculate length.

        Args:
            text: Text content for this chunk
        """
        self.content = text
        self.content_length = len(text)

    def set_position(self, start: int, end: int) -> None:
        """
        Set character position within source document.

        Args:
            start: Start character position
            end: End character position
        """
        self.start_char = start
        self.end_char = end

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<DocumentChunk("
            f"id={self.id}, "
            f"document_id={self.document_id}, "
            f"index={self.chunk_index}, "
            f"length={self.content_length}, "
            f"indexed={self.is_indexed}"
            f")>"
        )

    def __str__(self) -> str:
        """Human-readable string representation (truncated content)."""
        preview = (
            self.content[:100] + "..." if len(self.content) > 100 else self.content
        )
        return f"Chunk {self.chunk_index}: {preview}"
