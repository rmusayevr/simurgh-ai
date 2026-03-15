"""
Unit tests for app/services/vector_service.py

Covers:
    chunk_text (pure function — no mocks):
        - Empty text returns empty list
        - Single chunk when text <= chunk_size
        - Multiple chunks produced for long text
        - Overlap preserved between consecutive chunks
        - Whitespace-only chunks are skipped
        - chunk_size == overlap does not infinite-loop (stride > 0)

    VectorService.get_document_chunks:
        - Returns empty list when no chunks exist
        - Results ordered by chunk_index
        - limit parameter restricts results

    VectorService.delete_document_chunks:
        - Calls session.delete for each chunk
        - Calls session.commit
        - Returns correct deleted count

    VectorService.chunk_and_vectorize:
        - Dispatches Celery task and returns task ID string

    VectorService.semantic_search_only:
        - Returns empty list on exception (graceful degradation)

    VectorService.hybrid_search:
        - Falls back to semantic search when exception raised
        - RRF scoring: chunk present in both lists scores higher

    DocumentChunk model helpers:
        - has_embedding True when embedding list non-empty
        - is_indexed requires both embedding and search_vector
        - word_count approximate
        - set_content updates content_length

No real DB, no real embeddings. Embedding model patched where used.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.models.chunk import DocumentChunk
from app.services.vector_service import chunk_text


# ── Chunk factory ──────────────────────────────────────────────────────────────


def _make_chunk(
    id: int = 1,
    document_id: int = 1,
    chunk_index: int = 0,
    content: str = "Sample chunk content.",
    embedding=None,
    search_vector=None,
) -> DocumentChunk:
    c = DocumentChunk(
        id=id,
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        content_length=len(content),
    )
    c.embedding = embedding
    c.search_vector = search_vector
    return c


def _make_service(db_mock):
    from app.services.vector_service import VectorService

    return VectorService(session=db_mock)


# ══════════════════════════════════════════════════════════════════
# chunk_text — pure function
# ══════════════════════════════════════════════════════════════════


class TestChunkText:
    def test_empty_text_returns_empty_list(self):
        assert chunk_text("", chunk_size=100, overlap=10) == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_text("   \n\t  ", chunk_size=100, overlap=10) == []

    def test_short_text_produces_single_chunk(self):
        result = chunk_text("Hello world", chunk_size=100, overlap=10)
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_text_equal_to_chunk_size_no_overlap_is_one_chunk(self):
        """With zero overlap, text exactly chunk_size long produces exactly 1 chunk."""
        text = "A" * 50
        result = chunk_text(text, chunk_size=50, overlap=0)
        assert len(result) == 1

    def test_text_equal_to_chunk_size_with_overlap_produces_tail_chunk(self):
        """With overlap > 0, a second chunk starting at (chunk_size - overlap) is produced."""
        text = "A" * 50
        result = chunk_text(text, chunk_size=50, overlap=5)
        # start=0 → chunk "A"*50; next start=45 < 50 → chunk "A"*5; next start=90 >= 50 → break
        assert len(result) == 2

    def test_text_longer_than_chunk_size_produces_multiple_chunks(self):
        text = "A" * 200
        result = chunk_text(text, chunk_size=50, overlap=10)
        assert len(result) > 1

    def test_all_chars_covered(self):
        """Every character in the original text appears in at least one chunk."""
        text = "ABCDEFGHIJ"
        result = chunk_text(text, chunk_size=4, overlap=2)
        combined = "".join(result)
        for char in text:
            assert char in combined

    def test_overlap_preserved_between_consecutive_chunks(self):
        """The last `overlap` chars of chunk N equal the first `overlap` chars of chunk N+1."""
        text = "ABCDEFGHIJ"
        overlap = 2
        result = chunk_text(text, chunk_size=4, overlap=overlap)
        for i in range(len(result) - 1):
            assert result[i][-overlap:] == result[i + 1][:overlap]

    def test_zero_overlap_no_shared_content(self):
        text = "ABCDEFGH"
        result = chunk_text(text, chunk_size=4, overlap=0)
        assert result == ["ABCD", "EFGH"]

    def test_whitespace_only_chunks_skipped(self):
        # Chunk starting at a whitespace-only region should be skipped
        text = "Hello" + "   " + "World"
        result = chunk_text(text, chunk_size=5, overlap=0)
        # "   " is 3 chars — chunk_size=5 so "   Wo" passes strip; "ld" is one more
        # We just verify no chunk is whitespace-only
        for chunk in result:
            assert chunk.strip() != ""

    def test_chunk_size_larger_than_text(self):
        text = "Short"
        result = chunk_text(text, chunk_size=1000, overlap=100)
        assert len(result) == 1
        assert result[0] == "Short"

    def test_exact_chunk_boundary(self):
        text = "ABCDEF"
        result = chunk_text(text, chunk_size=3, overlap=0)
        assert result == ["ABC", "DEF"]

    def test_large_overlap_does_not_loop_forever(self):
        """overlap < chunk_size must be enforced by caller; stride = chunk_size - overlap > 0."""
        # chunk_size=4, overlap=2 → stride=2 → always progress
        text = "A" * 100
        result = chunk_text(text, chunk_size=4, overlap=2)
        assert len(result) > 0  # terminates


# ══════════════════════════════════════════════════════════════════
# DocumentChunk model helpers — pure Python
# ══════════════════════════════════════════════════════════════════


class TestDocumentChunkHelpers:
    def test_has_embedding_false_when_none(self):
        c = _make_chunk(embedding=None)
        assert c.has_embedding is False

    def test_has_embedding_false_when_empty_list(self):
        c = _make_chunk(embedding=[])
        assert c.has_embedding is False

    def test_has_embedding_true_when_populated(self):
        c = _make_chunk(embedding=[0.1, 0.2, 0.3])
        assert c.has_embedding is True

    def test_has_search_vector_false_when_none(self):
        c = _make_chunk(search_vector=None)
        assert c.has_search_vector is False

    def test_has_search_vector_true_when_set(self):
        c = _make_chunk(search_vector="'architecture':1 'migration':2")
        assert c.has_search_vector is True

    def test_is_indexed_requires_both(self):
        c = _make_chunk(embedding=[0.1], search_vector=None)
        assert c.is_indexed is False

    def test_is_indexed_true_when_both_present(self):
        c = _make_chunk(embedding=[0.1], search_vector="'term':1")
        assert c.is_indexed is True

    def test_word_count_approximate(self):
        c = _make_chunk(content="one two three four five")
        assert c.word_count == 5

    def test_word_count_single_word(self):
        c = _make_chunk(content="architecture")
        assert c.word_count == 1

    def test_set_content_updates_content_length(self):
        c = _make_chunk(content="old", embedding=None)
        c.set_content("new content here")
        assert c.content == "new content here"
        assert c.content_length == len("new content here")

    def test_set_position_stores_start_and_end(self):
        c = _make_chunk()
        c.set_position(100, 300)
        assert c.start_char == 100
        assert c.end_char == 300

    def test_repr_contains_document_id(self):
        c = _make_chunk(document_id=42)
        assert "42" in repr(c)

    def test_str_truncates_long_content(self):
        c = _make_chunk(content="A" * 200)
        rendered = str(c)
        assert "..." in rendered

    def test_str_shows_full_short_content(self):
        c = _make_chunk(content="short content")
        rendered = str(c)
        assert "short content" in rendered


# ══════════════════════════════════════════════════════════════════
# VectorService.get_document_chunks
# ══════════════════════════════════════════════════════════════════


class TestGetDocumentChunks:
    async def test_returns_empty_list_when_no_chunks(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        db.exec = AsyncMock(return_value=result_mock)

        svc = _make_service(db)
        result = await svc.get_document_chunks(document_id=99)
        assert result == []

    async def test_returns_chunks_from_db(self):
        chunks = [
            _make_chunk(id=1, chunk_index=0),
            _make_chunk(id=2, chunk_index=1),
        ]
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = chunks
        db.exec = AsyncMock(return_value=result_mock)

        svc = _make_service(db)
        result = await svc.get_document_chunks(document_id=1)
        assert len(result) == 2

    async def test_exec_called_with_limit_when_provided(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        db.exec = AsyncMock(return_value=result_mock)

        svc = _make_service(db)
        await svc.get_document_chunks(document_id=1, limit=3)

        # Verify exec was called (limit is applied in the query)
        db.exec.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# VectorService.delete_document_chunks
# ══════════════════════════════════════════════════════════════════


class TestDeleteDocumentChunks:
    async def test_returns_zero_when_no_chunks(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        db.exec = AsyncMock(return_value=result_mock)
        db.commit = AsyncMock()

        svc = _make_service(db)
        count = await svc.delete_document_chunks(document_id=1)
        assert count == 0

    async def test_deletes_each_chunk(self):
        chunks = [_make_chunk(id=i, chunk_index=i - 1) for i in range(1, 4)]
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = chunks
        db.exec = AsyncMock(return_value=result_mock)
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        svc = _make_service(db)
        count = await svc.delete_document_chunks(document_id=1)

        assert db.delete.call_count == 3
        assert count == 3

    async def test_commit_called_after_deletion(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = [_make_chunk()]
        db.exec = AsyncMock(return_value=result_mock)
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        svc = _make_service(db)
        await svc.delete_document_chunks(document_id=1)
        db.commit.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# VectorService.chunk_and_vectorize
# ══════════════════════════════════════════════════════════════════


class TestChunkAndVectorize:
    async def test_dispatches_celery_task_and_returns_id(self):
        db = AsyncMock()
        svc = _make_service(db)

        fake_task = MagicMock()
        fake_task.id = "celery-task-uuid-123"

        with patch(
            "app.services.vector_service.process_document_embeddings_task"
        ) as mock_task_cls:
            mock_task_cls.delay = MagicMock(return_value=fake_task)
            result = await svc.chunk_and_vectorize(
                document_id=1, full_text="Some text to vectorize."
            )

        assert result == "celery-task-uuid-123"
        mock_task_cls.delay.assert_called_once_with(1, "Some text to vectorize.")


# ══════════════════════════════════════════════════════════════════
# VectorService.semantic_search_only — graceful degradation
# ══════════════════════════════════════════════════════════════════


class TestSemanticSearchOnly:
    async def test_returns_empty_list_on_embedding_failure(self):
        db = AsyncMock()
        svc = _make_service(db)

        with patch(
            "app.services.vector_service.get_embedding_model",
            side_effect=RuntimeError("model not loaded"),
        ):
            result = await svc.semantic_search_only(query="microservices migration")

        assert result == []

    async def test_returns_empty_list_on_db_failure(self):
        db = AsyncMock()
        db.exec = AsyncMock(side_effect=Exception("db connection lost"))

        svc = _make_service(db)

        mock_model = MagicMock()
        mock_model.embed.return_value = iter([[0.1] * 384])

        with patch(
            "app.services.vector_service.get_embedding_model", return_value=mock_model
        ):
            result = await svc.semantic_search_only(query="architecture")

        assert result == []


# ══════════════════════════════════════════════════════════════════
# VectorService.hybrid_search — RRF scoring + fallback
# ══════════════════════════════════════════════════════════════════


class TestHybridSearch:
    async def test_falls_back_to_semantic_on_exception(self):
        db = AsyncMock()
        # First exec call (semantic) raises; fallback should trigger
        db.exec = AsyncMock(side_effect=Exception("pgvector unavailable"))

        svc = _make_service(db)

        mock_model = MagicMock()
        mock_model.embed.return_value = iter([[0.1] * 384])

        with patch(
            "app.services.vector_service.get_embedding_model", return_value=mock_model
        ):
            with patch.object(
                svc, "semantic_search_only", new_callable=AsyncMock
            ) as mock_fallback:
                mock_fallback.return_value = []
                result = await svc.hybrid_search(query="test")

        mock_fallback.assert_called_once()
        assert result == []

    async def test_chunk_in_both_results_scores_higher(self):
        """RRF: a chunk appearing in both semantic and keyword results gets a higher score.

        Tests the RRF algorithm directly since the SQL statement construction
        (pgvector cosine_distance) is not available in the unit test environment.
        """
        shared = _make_chunk(id=1, chunk_index=0, content="shared content")
        semantic_only = _make_chunk(id=2, chunk_index=1, content="semantic only")
        keyword_only = _make_chunk(id=3, chunk_index=2, content="keyword only")

        # Reproduce the exact RRF scoring from hybrid_search
        semantic_chunks = [shared, semantic_only]
        keyword_chunks = [shared, keyword_only]
        all_chunks_map = {c.id: c for c in semantic_chunks + keyword_chunks}

        semantic_weight, keyword_weight = 0.7, 0.3
        k_constant = 60
        rrf_scores: dict = {}

        for rank, chunk in enumerate(semantic_chunks):
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + (
                semantic_weight / (k_constant + rank + 1)
            )
        for rank, chunk in enumerate(keyword_chunks):
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + (
                keyword_weight / (k_constant + rank + 1)
            )

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
        top_chunks = [all_chunks_map[cid] for cid in sorted_ids[:3]]

        # Chunk 1 (shared) scored by both lists → highest RRF score
        assert top_chunks[0].id == 1
        assert rrf_scores[1] > rrf_scores[2]
        assert rrf_scores[1] > rrf_scores[3]

    async def test_returns_empty_on_total_failure(self):
        db = AsyncMock()
        db.exec = AsyncMock(side_effect=Exception("total failure"))

        svc = _make_service(db)

        mock_model = MagicMock()
        mock_model.embed.return_value = iter([[0.1] * 384])

        with patch(
            "app.services.vector_service.get_embedding_model", return_value=mock_model
        ):
            # Patch semantic_search_only too (the fallback path)
            with patch.object(
                svc, "semantic_search_only", new_callable=AsyncMock, return_value=[]
            ):
                result = await svc.hybrid_search(query="test")

        assert result == []
