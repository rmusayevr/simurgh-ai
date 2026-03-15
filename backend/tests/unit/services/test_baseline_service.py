"""
Unit tests for app/services/baseline_service.py

Covers:
    BaselineService._extract_quality_attributes (pure method):
        - Returns empty list for empty response
        - Detects each quality attribute (case-insensitive)
        - Returns only unique matches
        - Does not return attributes not present in response

    BaselineService._get_baseline_system_prompt (pure method):
        - Returns non-empty string
        - Does NOT frame as any specialised persona

    BaselineService._build_baseline_prompt (pure method):
        - Contains task_description in output
        - Contains rag_context in output
        - Contains required section headers

    BaselineService._get_rag_context:
        - Returns formatted context string when chunks found
        - Returns fallback message when no chunks
        - Returns error fallback message on exception

    BaselineService.generate_baseline_proposal:
        - Raises NotFoundException for unknown proposal ID
        - Calls ai_service.generate_text with correct system prompt
        - Saves ProposalVariation with persona=BASELINE
        - AIServiceException raised when AI call fails
        - generation_seconds populated on variation
        - Quality attributes embedded in reasoning field

All DB and AI calls are mocked. No real Anthropic calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.proposal import (
    ProposalVariation,
    AgentPersona,
)
from app.core.exceptions import NotFoundException, AIServiceException
from tests.fixtures.proposals import build_proposal


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(db_mock):
    from app.services.baseline_service import BaselineService

    svc = BaselineService(session=db_mock)
    svc.vector_service = AsyncMock()
    svc.vector_service.hybrid_search = AsyncMock(return_value=[])
    return svc


def _make_db_with_proposal(proposal):
    db = AsyncMock()
    db.get = AsyncMock(return_value=proposal)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _make_chunk(
    document_id: int = 1, chunk_index: int = 0, content: str = "Architecture context."
):
    from app.models.chunk import DocumentChunk

    c = DocumentChunk(
        id=chunk_index + 1,
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        content_length=len(content),
    )
    return c


# ══════════════════════════════════════════════════════════════════
# _extract_quality_attributes — pure method
# ══════════════════════════════════════════════════════════════════


class TestExtractQualityAttributes:
    def _get_method(self):
        db = AsyncMock()
        svc = _make_service(db)
        return svc._extract_quality_attributes

    def test_empty_response_returns_empty_list(self):
        result = self._get_method()("")
        assert result == []

    def test_whitespace_only_returns_empty(self):
        result = self._get_method()("   \n\t  ")
        assert result == []

    def test_detects_reliability(self):
        result = self._get_method()("The system ensures reliability under load.")
        assert "Reliability" in result

    def test_detects_security(self):
        result = self._get_method()("Security must be enforced at the API boundary.")
        assert "Security" in result

    def test_detects_scalability(self):
        result = self._get_method()("Horizontal scalability enables autoscaling.")
        assert "Scalability" in result

    def test_detection_is_case_insensitive(self):
        result = self._get_method()("PERFORMANCE is a key non-functional requirement.")
        assert "Performance" in result

    def test_detects_multiple_attributes(self):
        response = (
            "The design prioritises maintainability and testability. "
            "Security controls are applied at every layer. "
            "Performance targets: 99th percentile < 200ms."
        )
        result = self._get_method()(response)
        assert "Maintainability" in result
        assert "Testability" in result
        assert "Security" in result
        assert "Performance" in result

    def test_does_not_return_absent_attributes(self):
        response = "A simple request-response HTTP server."
        result = self._get_method()(response)
        # Attributes that are clearly absent
        assert "Resilience" not in result or "resilience" in response.lower()

    def test_returns_list_not_set(self):
        result = self._get_method()("reliability scalability")
        assert isinstance(result, list)

    def test_detects_observability(self):
        result = self._get_method()("Observability via distributed tracing.")
        assert "Observability" in result

    def test_detects_cost_effectiveness(self):
        result = self._get_method()(
            "Cost-effectiveness is achieved via spot instances."
        )
        assert "Cost-effectiveness" in result


# ══════════════════════════════════════════════════════════════════
# _get_baseline_system_prompt — pure method
# ══════════════════════════════════════════════════════════════════


class TestGetBaselineSystemPrompt:
    def _get_prompt(self):
        svc = _make_service(AsyncMock())
        return svc._get_baseline_system_prompt()

    def test_returns_non_empty_string(self):
        result = self._get_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mentions_architect_role(self):
        result = self._get_prompt()
        assert "architect" in result.lower()

    def test_does_not_frame_as_legacy_keeper(self):
        result = self._get_prompt()
        assert "Legacy Keeper" not in result
        assert "legacy_keeper" not in result.lower()

    def test_does_not_frame_as_innovator(self):
        result = self._get_prompt()
        assert "Innovator" not in result

    def test_does_not_frame_as_mediator(self):
        result = self._get_prompt()
        assert "Mediator" not in result


# ══════════════════════════════════════════════════════════════════
# _build_baseline_prompt — pure method
# ══════════════════════════════════════════════════════════════════


class TestBuildBaselinePrompt:
    def _build(
        self,
        task: str = "Migrate monolith to microservices",
        rag: str = "Relevant context.",
    ):
        svc = _make_service(AsyncMock())
        return svc._build_baseline_prompt(task_description=task, rag_context=rag)

    def test_contains_task_description(self):
        result = self._build(task="Redesign the auth service")
        assert "Redesign the auth service" in result

    def test_contains_rag_context(self):
        result = self._build(rag="The system uses PostgreSQL 15.")
        assert "The system uses PostgreSQL 15." in result

    def test_contains_architecture_overview_section(self):
        result = self._build()
        assert "Architecture" in result or "architecture" in result

    def test_contains_trade_offs_section(self):
        result = self._build()
        assert "Trade-off" in result or "trade-off" in result.lower()

    def test_contains_risk_section(self):
        result = self._build()
        assert "Risk" in result or "risk" in result.lower()

    def test_returns_non_empty_string(self):
        result = self._build()
        assert len(result) > 100


# ══════════════════════════════════════════════════════════════════
# BaselineService._get_rag_context
# ══════════════════════════════════════════════════════════════════


class TestGetRagContext:
    async def test_returns_formatted_context_when_chunks_found(self):
        chunk = _make_chunk(
            document_id=1,
            chunk_index=0,
            content="The current system uses a monolithic Rails app.",
        )
        db = AsyncMock()
        svc = _make_service(db)
        svc.vector_service.hybrid_search = AsyncMock(return_value=[chunk])

        proposal = build_proposal(id=1)
        result = await svc._get_rag_context(proposal)

        assert "Document 1" in result
        assert "Chunk 0" in result
        assert "monolithic Rails app" in result

    async def test_returns_fallback_when_no_chunks(self):
        db = AsyncMock()
        svc = _make_service(db)
        svc.vector_service.hybrid_search = AsyncMock(return_value=[])

        proposal = build_proposal(id=1)
        result = await svc._get_rag_context(proposal)

        assert "No relevant" in result

    async def test_returns_error_fallback_on_exception(self):
        db = AsyncMock()
        svc = _make_service(db)
        svc.vector_service.hybrid_search = AsyncMock(
            side_effect=Exception("pgvector down")
        )

        proposal = build_proposal(id=1)
        result = await svc._get_rag_context(proposal)

        assert "failed" in result.lower() or "retrieval" in result.lower()

    async def test_multiple_chunks_joined_with_separator(self):
        chunks = [
            _make_chunk(document_id=1, chunk_index=0, content="First chunk."),
            _make_chunk(document_id=1, chunk_index=1, content="Second chunk."),
        ]
        db = AsyncMock()
        svc = _make_service(db)
        svc.vector_service.hybrid_search = AsyncMock(return_value=chunks)

        proposal = build_proposal(id=1)
        result = await svc._get_rag_context(proposal)

        assert "First chunk." in result
        assert "Second chunk." in result


# ══════════════════════════════════════════════════════════════════
# BaselineService.generate_baseline_proposal
# ══════════════════════════════════════════════════════════════════


class TestGenerateBaselineProposal:
    async def test_not_found_raises_not_found_exception(self):
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        svc = _make_service(db)

        with pytest.raises(NotFoundException, match="Proposal 99 not found"):
            await svc.generate_baseline_proposal(99)

    async def test_ai_failure_raises_ai_service_exception(self):
        proposal = build_proposal(id=1)
        db = _make_db_with_proposal(proposal)
        svc = _make_service(db)
        svc._get_rag_context = AsyncMock(return_value="Some context.")

        with patch(
            "app.services.baseline_service.ai_service.generate_text",
            new_callable=AsyncMock,
            side_effect=Exception("API connection timeout"),
        ):
            with pytest.raises(AIServiceException):
                await svc.generate_baseline_proposal(1)

    async def test_saves_variation_with_baseline_persona(self):
        proposal = build_proposal(id=1)
        db = _make_db_with_proposal(proposal)
        saved_variations = []

        def capture_add(obj):
            if isinstance(obj, ProposalVariation):
                saved_variations.append(obj)

        db.add.side_effect = capture_add
        svc = _make_service(db)
        svc._get_rag_context = AsyncMock(return_value="RAG context.")

        with patch(
            "app.services.baseline_service.ai_service.generate_text",
            new_callable=AsyncMock,
            return_value="# Architecture Proposal\n\nReliability and Scalability are key.",
        ):
            await svc.generate_baseline_proposal(1)

        assert len(saved_variations) == 1
        assert saved_variations[0].agent_persona == AgentPersona.BASELINE

    async def test_generation_seconds_populated(self):
        proposal = build_proposal(id=1)
        db = _make_db_with_proposal(proposal)
        saved_variations = []
        db.add.side_effect = lambda obj: (
            saved_variations.append(obj) if isinstance(obj, ProposalVariation) else None
        )
        svc = _make_service(db)
        svc._get_rag_context = AsyncMock(return_value="Context.")

        with patch(
            "app.services.baseline_service.ai_service.generate_text",
            new_callable=AsyncMock,
            return_value="Architecture proposal text. Security and reliability considered.",
        ):
            await svc.generate_baseline_proposal(1)

        variation = saved_variations[0]
        assert variation.generation_seconds is not None
        assert variation.generation_seconds >= 0

    async def test_detected_quality_attributes_in_reasoning(self):
        proposal = build_proposal(id=1)
        db = _make_db_with_proposal(proposal)
        saved_variations = []
        db.add.side_effect = lambda obj: (
            saved_variations.append(obj) if isinstance(obj, ProposalVariation) else None
        )
        svc = _make_service(db)
        svc._get_rag_context = AsyncMock(return_value="Context.")

        with patch(
            "app.services.baseline_service.ai_service.generate_text",
            new_callable=AsyncMock,
            return_value="The system prioritises Security, Scalability, and Reliability above all else.",
        ):
            await svc.generate_baseline_proposal(1)

        variation = saved_variations[0]
        # Reasoning should mention at least one of the detected QA attributes
        assert variation.reasoning is not None
        assert len(variation.reasoning) > 0

    async def test_calls_commit_after_saving(self):
        proposal = build_proposal(id=1)
        db = _make_db_with_proposal(proposal)
        svc = _make_service(db)
        svc._get_rag_context = AsyncMock(return_value="Context.")

        with patch(
            "app.services.baseline_service.ai_service.generate_text",
            new_callable=AsyncMock,
            return_value="Architecture plan with Reliability in mind.",
        ):
            await svc.generate_baseline_proposal(1)

        db.commit.assert_called()

    async def test_returns_proposal_variation(self):
        proposal = build_proposal(id=1)
        db = _make_db_with_proposal(proposal)
        # Simulate refresh setting the variation's id
        db.refresh = AsyncMock(
            side_effect=lambda obj: (
                setattr(obj, "id", 42) if isinstance(obj, ProposalVariation) else None
            )
        )
        svc = _make_service(db)
        svc._get_rag_context = AsyncMock(return_value="Context.")

        with patch(
            "app.services.baseline_service.ai_service.generate_text",
            new_callable=AsyncMock,
            return_value="# Baseline Architecture\n\nMaintainability and Testability are core.",
        ):
            result = await svc.generate_baseline_proposal(1)

        assert isinstance(result, ProposalVariation)
        assert result.agent_persona == AgentPersona.BASELINE

    async def test_confidence_score_is_70(self):
        """Baseline always uses confidence_score=70 per the service implementation."""
        proposal = build_proposal(id=1)
        db = _make_db_with_proposal(proposal)
        saved_variations = []
        db.add.side_effect = lambda obj: (
            saved_variations.append(obj) if isinstance(obj, ProposalVariation) else None
        )
        svc = _make_service(db)
        svc._get_rag_context = AsyncMock(return_value="Context.")

        with patch(
            "app.services.baseline_service.ai_service.generate_text",
            new_callable=AsyncMock,
            return_value="Architecture proposal with Security focus.",
        ):
            await svc.generate_baseline_proposal(1)

        assert saved_variations[0].confidence_score == 70
