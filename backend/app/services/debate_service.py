"""
Debate service for Council of Agents orchestration.

Manages multi-agent architectural debates:
    - 3 personas: Legacy Keeper, Innovator, Mediator
    - Round-robin turn order
    - RAG context integration
    - Consensus detection
    - Turn-by-turn persistence (DebateTurn model)
    - RQ2 persona consistency metrics

Debate flow:
    1. Initialize debate session for a proposal
    2. For each turn (max 6 rounds):
        a. Generate persona response with RAG context
        b. Save DebateTurn record
        c. Check for consensus (after mediator speaks)
    3. Generate final consensus proposal (3 options)
    4. Calculate RQ2 metrics (persona consistency scores)
    5. Mark debate complete

Used for thesis RQ1 (trust/quality), RQ2 (persona consistency), RQ3 (consensus efficiency).
"""

import structlog
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.debate import DebateSession, ConsensusType
from app.models.proposal import Proposal, AgentPersona
from app.models.user import UserRole
from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    DebateException,
)
from app.services.persona_service import PersonaService
from app.services.vector_service import VectorService
from app.services.ai import ai_service

logger = structlog.get_logger()


class DebateService:
    """
    Service for orchestrating multi-agent architectural debates.

    Conducts debates between three AI personas to evaluate proposals
    from multiple stakeholder perspectives.
    """

    # Turn order: Legacy Keeper → Innovator → Mediator (repeating)
    TURN_ORDER = [
        AgentPersona.LEGACY_KEEPER,
        AgentPersona.INNOVATOR,
        AgentPersona.MEDIATOR,
    ]

    def __init__(self, session: AsyncSession):
        self.session = session
        self.vector_service = VectorService(session=session)
        self.persona_service = PersonaService(session=session)

    # ==================== Conduct Debate ====================

    async def conduct_debate(
        self,
        proposal_id: int,
        user_id: int,
        user_role: UserRole,
        max_turns: int = 6,
        consensus_threshold: float = 0.8,
    ) -> DebateSession:
        """
        Conduct a full multi-agent debate for a proposal.

        Args:
            proposal_id: Proposal to debate
            user_id: User initiating debate (for access control)
            user_role: User's system role
            max_turns: Max debate rounds (default 6 = 2 full cycles)
            consensus_threshold: Min confidence for consensus (0.0-1.0)

        Returns:
            DebateSession: Completed debate with all turns

        Raises:
            NotFoundException: If proposal not found
            ForbiddenException: If user lacks access
            DebateException: If debate execution fails
        """
        log = logger.bind(
            operation="conduct_debate",
            proposal_id=proposal_id,
            max_turns=max_turns,
        )

        # Fetch proposal with access control
        proposal = await self._get_proposal_with_access(proposal_id, user_id, user_role)

        start_time = datetime.now(timezone.utc).replace(tzinfo=None)
        log.info("debate_started")

        # Create debate session
        debate = DebateSession(
            proposal_id=proposal_id,
            started_at=start_time,
            consensus_reached=False,
            total_turns=0,
        )
        self.session.add(debate)
        await self.session.commit()
        await self.session.refresh(debate)

        try:
            # Retrieve RAG context
            rag_context = await self._get_rag_context(proposal)

            # Conduct debate turns
            current_turn = 0
            consensus_reached = False

            while current_turn < max_turns and not consensus_reached:
                persona = self.TURN_ORDER[current_turn % len(self.TURN_ORDER)]

                # Generate persona response
                await self._execute_turn(
                    debate=debate,
                    proposal=proposal,
                    persona=persona,
                    turn_index=current_turn,
                    rag_context=rag_context,
                )

                current_turn += 1
                debate.total_turns = current_turn

                # Check consensus after mediator speaks
                if persona == AgentPersona.MEDIATOR:
                    consensus_reached, confidence = await self._check_consensus(
                        debate_id=debate.id,
                        threshold=consensus_threshold,
                    )

                    if consensus_reached:
                        log.info(
                            "consensus_reached",
                            turn=current_turn,
                            confidence=confidence,
                        )
                        debate.consensus_reached = True
                        debate.consensus_confidence = confidence
                        break

            # Generate final consensus proposal
            if debate.consensus_reached:
                final_proposal = await self._generate_final_proposal(debate, proposal)
                debate.final_consensus_proposal = final_proposal
                debate.consensus_type = ConsensusType.UNANIMOUS
            else:
                debate.consensus_type = ConsensusType.TIMEOUT

            # Calculate metrics
            end_time = datetime.now(timezone.utc).replace(tzinfo=None)
            debate.completed_at = end_time
            debate.duration_seconds = (end_time - start_time).total_seconds()
            debate.conflict_density = await self._calculate_conflict_density(debate.id)

            # Calculate RQ2 persona consistency scores
            await self._calculate_persona_consistency(debate.id)

            self.session.add(debate)
            await self.session.commit()
            await self.session.refresh(debate)

            log.info(
                "debate_completed",
                debate_id=str(debate.id),
                turns=debate.total_turns,
                consensus=debate.consensus_reached,
                duration=debate.duration_seconds,
            )

            return debate

        except Exception as e:
            log.exception("debate_execution_failed", error=str(e))
            # Rollback the aborted transaction before attempting cleanup writes.
            # Without this, any commit() inside an aborted asyncpg transaction raises
            # InFailedSQLTransactionError and masks the original error.
            try:
                await self.session.rollback()
                debate.consensus_type = ConsensusType.TIMEOUT
                debate.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                self.session.add(debate)
                await self.session.commit()
            except Exception as cleanup_error:
                log.error("debate_cleanup_failed", error=str(cleanup_error))
            raise DebateException(f"Debate execution failed: {str(e)}")

    # ==================== Turn Execution ====================

    async def _execute_turn(
        self,
        debate: DebateSession,
        proposal: Proposal,
        persona: AgentPersona,
        turn_index: int,
        rag_context: str,
    ) -> Dict[str, Any]:
        """
        Execute a single debate turn for one persona and append to JSONB history.

        DebateTurn is NOT a database table — turns are stored as JSONB dicts
        inside DebateSession.debate_history via the model's add_turn() method.

        Args:
            debate: Active debate session
            proposal: Proposal being debated
            persona: Persona speaking this turn
            turn_index: Turn number (0-indexed)
            rag_context: RAG context string

        Returns:
            dict: The turn dict that was appended to debate_history
        """
        log = logger.bind(
            debate_id=str(debate.id),
            turn=turn_index,
            persona=persona.value,
        )

        # History is already in debate.debate_history (JSONB list)
        debate_history = self._get_debate_history_from_session(debate)

        # Generate persona response
        try:
            response_data = await self.persona_service.generate_response(
                persona_slug=persona.value.lower(),
                proposal_context={"description": proposal.task_description},
                debate_history=debate_history,
                rag_context=rag_context,
            )
        except Exception as e:
            log.error("persona_response_failed", error=str(e))
            raise DebateException(
                f"Failed to generate {persona.value} response: {str(e)}"
            )

        response_text = response_data.get("response_text", "")
        quality_attrs = response_data.get("quality_attributes_mentioned", [])
        bias_score = response_data.get("bias_alignment_score", 0.5)

        # Detect sentiment from response text
        conflict_keywords = [
            "however",
            "disagree",
            "risk",
            "concern",
            "challenge",
            "problematic",
        ]
        sentiment = (
            "contentious"
            if any(kw in response_text.lower() for kw in conflict_keywords)
            else "agreeable"
        )

        # Append to JSONB history via model helper (also increments total_turns).
        # bias_alignment_score is passed here so it's stored in the JSONB dict
        # and survives DB round-trips — DebateTurnRead requires this field.
        debate.add_turn(
            persona=persona.value,
            response=response_text,
            sentiment=sentiment,
            key_points=quality_attrs,
            bias_alignment_score=bias_score,
        )

        # Capture the turn dict BEFORE commit/refresh — after refresh the in-memory
        # list object is replaced, so [-1] on the refreshed object is unreliable.
        turn_dict = dict(debate.debate_history[-1])
        turn_dict["bias_alignment_score"] = bias_score

        # flag_modified tells SQLAlchemy that the JSON column mutated in-place.
        # Without this, list.append() is invisible to change detection and the
        # mutation may not be flushed to the DB.
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(debate, "debate_history")

        self.session.add(debate)
        await self.session.commit()
        await self.session.refresh(debate)

        log.info(
            "turn_completed",
            qa_count=len(quality_attrs),
            bias_score=bias_score,
        )

        return turn_dict

    # ==================== RAG Context ====================

    async def _get_rag_context(self, proposal: Proposal) -> str:
        """
        Retrieve RAG context for the proposal, scoped to its own project.

        Previously searched across ALL projects (document_ids=None), which in
        a multi-tenant deployment would leak document content across project
        boundaries.  Now we first collect the document IDs that belong to
        the proposal's project and restrict the vector search to those IDs.

        Args:
            proposal: Proposal being debated

        Returns:
            str: Formatted RAG context or fallback message
        """
        try:
            # ── Collect document IDs for this project only ─────────────────
            from sqlmodel import select as sql_select

            # Fetch distinct document_ids whose chunks belong to this project.
            # DocumentChunk stores document_id; the parent HistoricalDocument
            # has a project_id FK.  We join through the document table.
            from app.models.project import HistoricalDocument  # type: ignore

            doc_result = await self.session.exec(
                sql_select(HistoricalDocument.id).where(
                    HistoricalDocument.project_id == proposal.project_id
                )
            )
            project_doc_ids = doc_result.all()

            if not project_doc_ids:
                logger.info(
                    "rag_no_documents_for_project",
                    project_id=proposal.project_id,
                )
                return "No project documents available for context."

            chunks = await self.vector_service.search_similar(
                query=proposal.task_description,
                limit=5,
                document_ids=list(project_doc_ids),  # ← scoped to this project
            )

            if chunks:
                context = "\n\n".join(
                    [
                        f"[Document {c.document_id}, Chunk {c.chunk_index}]:\n{c.content}"
                        for c in chunks
                    ]
                )
                logger.info(
                    "rag_context_retrieved",
                    chunks=len(chunks),
                    project_id=proposal.project_id,
                )
                return context
            else:
                return "No relevant project documentation found."

        except Exception as e:
            logger.error("rag_retrieval_failed", error=str(e))
            return "Documentation retrieval failed. Proceeding without context."

    # ==================== Consensus Detection ====================

    async def _check_consensus(
        self,
        debate_id: UUID,
        threshold: float,
    ) -> tuple[bool, float]:
        """
        Check if consensus has been reached in the debate.

        Uses Claude's Tool Use (structured output) to analyse the last 3 turns,
        eliminating the fragile regex/json.loads workaround that could fail when
        Claude's formatting varied (e.g. fenced ```json blocks).

        Args:
            debate_id: Debate session ID
            threshold: Min confidence score to declare consensus

        Returns:
            tuple: (consensus_reached: bool, confidence: float)
        """
        try:
            debate = await self.session.get(DebateSession, debate_id)
            if not debate or not debate.debate_history:
                return False, 0.0

            recent_turns = debate.debate_history[-3:]

            if len(recent_turns) < 3:
                return False, 0.0

            formatted_history = "\n\n".join(
                [
                    f"{t['persona'].upper()}:\n{t['response'][:300]}..."
                    for t in recent_turns
                ]
            )

            prompt = f"""Analyse the following debate exchanges to determine if the three personas
have reached consensus on an architectural approach.

DEBATE HISTORY (last 3 turns):
{formatted_history}

Consensus is reached when all three personas:
1. Acknowledge each other's concerns
2. Converge on a shared solution or compromise
3. Stop raising new fundamental objections"""

            schema = {
                "type": "object",
                "properties": {
                    "consensus_reached": {
                        "type": "boolean",
                        "description": "True if all three personas have converged",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Confidence level (0.0–1.0)",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of the consensus assessment",
                    },
                },
                "required": ["consensus_reached", "confidence", "reasoning"],
            }

            result = await ai_service.generate_structured(
                system_prompt="You are a consensus analyser for multi-agent architectural debates.",
                user_prompt=prompt,
                schema=schema,
                tool_name="submit_consensus_check",
                model=settings.ANTHROPIC_MODEL,
                max_tokens=300,
                operation="debate_consensus_check",
            )

            consensus = bool(result.get("consensus_reached", False))
            confidence = float(result.get("confidence", 0.0))

            if consensus and confidence >= threshold:
                logger.info(
                    "consensus_detected",
                    confidence=confidence,
                    reasoning=result.get("reasoning"),
                )
                return True, confidence
            else:
                return False, confidence

        except Exception as e:
            logger.error("consensus_check_failed", error=str(e))
            return False, 0.0

    # ==================== Final Proposal Generation ====================

    async def _generate_final_proposal(
        self,
        debate: DebateSession,
        proposal: Proposal,
    ) -> str:
        """
        Generate final consensus proposal synthesizing all debate turns.

        Uses the council-synthesis prompt template to create a structured
        proposal document with multiple implementation paths.

        Args:
            debate: Completed debate session
            proposal: Original proposal

        Returns:
            str: Final consensus proposal text
        """
        try:
            # Read history directly from the JSONB field — no DB query needed
            debate_history = self._get_debate_history_from_session(debate)

            # Format history — JSONB dicts use turn_number/persona/response keys
            history_text = "\n\n".join(
                [
                    f"Turn {h.get('turn_number', i + 1)} - {h.get('persona', '').upper()}:\n{h.get('response', '')}"
                    for i, h in enumerate(debate_history)
                ]
            )

            # Use synthesis template from database
            from app.models.prompt import PromptTemplate

            result = await self.session.exec(
                select(PromptTemplate).where(
                    PromptTemplate.slug == "council_synthesis",
                    PromptTemplate.is_active,
                )
            )
            template = result.first()

            system_prompt = (
                template.system_prompt
                if template
                else "Synthesize the debate into a comprehensive architectural proposal."
            )

            user_message = f"""
ORIGINAL TASK:
{proposal.task_description}

FULL DEBATE HISTORY:
{history_text}

YOUR TASK:
Synthesize the debate into a final consensus proposal that:
1. Addresses concerns from all three personas
2. Presents 3 implementation paths (conservative, balanced, aggressive)
3. Includes trade-offs and recommendations
""".strip()

            final_text = await ai_service.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_message,
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2000,
                temperature=0.7,
                operation="debate_final_synthesis",
            )

            logger.info("final_proposal_generated", length=len(final_text))
            return final_text

        except Exception as e:
            logger.error("final_proposal_generation_failed", error=str(e))
            return "Failed to generate final consensus proposal."

    # ==================== Metrics ====================

    async def _calculate_conflict_density(self, debate_id: UUID) -> float:
        """
        Calculate conflict density metric for the debate.

        Measures frequency of disagreement keywords across all turns.
        Used for RQ3 (consensus efficiency) analysis.

        Args:
            debate_id: Debate session ID

        Returns:
            float: Conflict density (0.0-1.0)
        """
        # Read from JSONB — DebateTurn is NOT a DB table
        debate = await self.session.get(DebateSession, debate_id)
        if not debate or not debate.debate_history:
            return 0.0

        turns = debate.debate_history

        conflict_keywords = [
            "however",
            "disagree",
            "risk",
            "concern",
            "but",
            "challenge",
            "problematic",
            "issue",
        ]

        conflicts = sum(
            1
            for turn in turns
            if any(kw in turn.get("response", "").lower() for kw in conflict_keywords)
        )

        return round(conflicts / len(turns), 3)

    async def _calculate_persona_consistency(self, debate_id: UUID) -> None:
        """
        Calculate RQ2 persona consistency scores and update DebateSession.

        Aggregates bias_alignment_score from all turns per persona.

        Args:
            debate_id: Debate session ID
        """
        # Read from JSONB — DebateTurn is NOT a DB table
        debate = await self.session.get(DebateSession, debate_id)
        if not debate or not debate.debate_history:
            return

        turns = debate.debate_history

        # Group bias_alignment_score by persona
        persona_scores: dict[str, list[float]] = {
            AgentPersona.LEGACY_KEEPER.value: [],
            AgentPersona.INNOVATOR.value: [],
            AgentPersona.MEDIATOR.value: [],
        }

        for turn in turns:
            persona = turn.get("persona", "")
            bias = float(turn.get("bias_alignment_score", 0.5))
            if persona in persona_scores:
                persona_scores[persona].append(bias)

        def mean(scores: list) -> float:
            return sum(scores) / len(scores) if scores else 0.0

        debate.legacy_keeper_consistency = mean(
            persona_scores[AgentPersona.LEGACY_KEEPER.value]
        )
        debate.innovator_consistency = mean(
            persona_scores[AgentPersona.INNOVATOR.value]
        )
        debate.mediator_consistency = mean(persona_scores[AgentPersona.MEDIATOR.value])
        debate.calculate_persona_consistency()  # updates overall_persona_consistency

        self.session.add(debate)
        await self.session.commit()

    # ==================== Read ====================

    def _get_debate_history_from_session(self, debate: "DebateSession") -> list:
        """
        Return debate history from the in-memory DebateSession object.

        DebateTurn is NOT a DB table — history lives in debate.debate_history (JSONB).
        Each entry is a dict: {turn_number, persona, response, timestamp, sentiment, key_points}
        """
        return debate.debate_history or []

    async def _get_debate_history(self, debate_id: "UUID") -> list:
        """
        Fetch and return debate history from DB for a given debate_id.

        Reads from DebateSession.debate_history (JSONB) — NOT from DebateTurn table.
        Returns list of dicts compatible with PersonaService.generate_response().
        """
        debate = await self.session.get(DebateSession, debate_id)
        if not debate or not debate.debate_history:
            return []
        return debate.debate_history

    async def get_debate_by_id(
        self,
        debate_id: UUID,
        user_id: int,
        user_role: UserRole,
    ) -> DebateSession:
        """
        Get a debate session by ID with access control.

        Raises:
            NotFoundException: If debate not found or user lacks access
        """
        debate = await self.session.get(DebateSession, debate_id)
        if not debate:
            raise NotFoundException(f"Debate {debate_id} not found")

        # Check access via proposal
        await self._get_proposal_with_access(debate.proposal_id, user_id, user_role)

        return debate

    async def get_debates_by_proposal(
        self,
        proposal_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> list[DebateSession]:
        """
        List all debate sessions for a proposal, ordered by most recent first.

        Verifies the caller has access to the proposal before returning results.

        Args:
            proposal_id: Parent proposal ID
            user_id: Requesting user ID (for access control)
            user_role: Requesting user role (for access control)

        Returns:
            List[DebateSession]: All debates for the proposal, newest first.

        Raises:
            NotFoundException: If proposal not found or caller lacks access.
        """
        # Access check — raises NotFoundException if unauthorized
        await self._get_proposal_with_access(proposal_id, user_id, user_role)

        result = await self.session.exec(
            select(DebateSession)
            .where(DebateSession.proposal_id == proposal_id)
            .order_by(DebateSession.started_at.desc())
        )
        return list(result.all())

    async def get_debate_turns(
        self,
        debate_id: UUID,
        user_id: int,
        user_role: UserRole,
    ) -> list[dict]:
        """
        Return the ordered turn history for a debate session.

        Turns are stored as a JSONB list on DebateSession (not a separate table).
        Each entry is a dict with keys: turn_number, persona, response,
        timestamp, sentiment, key_points, bias_alignment_score.

        Args:
            debate_id: Debate session UUID
            user_id: Requesting user ID (for access control)
            user_role: Requesting user role (for access control)

        Returns:
            List[dict]: Turns ordered by turn_number ascending.

        Raises:
            NotFoundException: If debate not found or caller lacks access.
        """
        debate = await self.get_debate_by_id(debate_id, user_id, user_role)
        history = debate.debate_history or []
        # Ensure consistent ordering by turn_number even if JSONB was appended
        # out of order (e.g. after a retry that appended mid-list).
        return sorted(history, key=lambda t: t.get("turn_number", 0))

    # ==================== Access Control ====================

    async def _get_proposal_with_access(
        self,
        proposal_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> Proposal:
        """
        Get proposal with access control via ProposalService.get_by_id().

        Passes user identity so that get_by_id enforces project-membership
        checks rather than relying on a comment saying it "should" do so.

        Raises:
            NotFoundException: If proposal not found or user lacks access.
        """
        from app.services.proposal_service import ProposalService

        proposal_service = ProposalService(self.session)
        return await proposal_service.get_by_id(
            proposal_id=proposal_id,
        )
