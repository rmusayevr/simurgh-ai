"""
Persona coding service for thesis RQ2 validation.

Handles manual coding workflow for validating AI persona consistency:
    - Submit coding records for debate turns
    - Update existing codings (inter-rater reliability)
    - Generate RQ2 summary reports per debate
    - Export data for statistical analysis (SPSS/R)
    - Calculate persona consistency metrics

RQ2: "Do AI personas maintain consistent character throughout debates?"

Methodology:
    1. Researcher randomly samples ~20% of debate turns
    2. Manually codes each turn for:
       - In-character rating (YES/PARTIAL/NO)
       - Quality attributes mentioned
       - Hallucination severity (NONE/MINOR/MAJOR)
       - Bias alignment (boolean)
    3. Calculate inter-rater reliability if multiple coders
    4. Aggregate into debate-level consistency scores
    5. Write scores back to DebateSession model
"""

import structlog
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.persona_coding import (
    PersonaCoding,
    InCharacterRating,
    HallucinationRating,
)
from app.models.debate import DebateSession
from app.models.proposal import AgentPersona
from app.schemas.persona_coding import (
    PersonaCodingCreate,
    PersonaCodingUpdate,
    PersonaCodingSummary,
    PersonaConsistencyBreakdown,
)
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)

logger = structlog.get_logger()


class PersonaCodingService:
    """
    Service for managing manual persona consistency coding.

    Used by researchers to validate RQ2 (persona consistency)
    through manual analysis of debate turns.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Create ====================

    async def submit_coding(
        self,
        data: PersonaCodingCreate,
    ) -> PersonaCoding:
        """
        Submit a manual coding record for a debate turn.

        Enforces uniqueness: one coder can only code each turn once.

        Args:
            data: Coding data (debate_id, turn_index, ratings, etc.)

        Returns:
            PersonaCoding: Created coding record

        Raises:
            BadRequestException: If validation fails or duplicate coding
        """
        log = logger.bind(
            operation="submit_coding",
            debate_id=str(data.debate_id),
            turn_index=data.turn_index,
        )

        # Check for duplicate coding
        existing = await self._get_existing_coding(
            debate_id=data.debate_id,
            turn_index=data.turn_index,
            coder_id=data.coder_id,
        )

        if existing:
            raise BadRequestException(
                f"You have already coded turn {data.turn_index} of this debate. "
                "Use the update endpoint to modify your coding."
            )

        # Create coding record
        coding = PersonaCoding(
            debate_id=data.debate_id,
            turn_index=data.turn_index,
            persona=data.persona,
            in_character=data.in_character,
            quality_attributes=data.quality_attributes,
            hallucination=data.hallucination,
            bias_alignment=data.bias_alignment,
            notes=data.notes,
            evidence_quote=data.evidence_quote,
            coder_id=data.coder_id,
            coding_duration_seconds=data.coding_duration_seconds,
        )

        self.session.add(coding)
        await self.session.commit()
        await self.session.refresh(coding)

        log.info(
            "coding_submitted",
            coding_id=str(coding.id),
            in_character=coding.in_character.value,
            hallucination=coding.hallucination.value,
        )

        return coding

    # ==================== Read ====================

    async def get_coding_by_id(self, coding_id: UUID) -> PersonaCoding:
        """
        Get a coding record by ID.

        Raises:
            NotFoundException: If coding not found
        """
        coding = await self.session.get(PersonaCoding, coding_id)
        if not coding:
            raise NotFoundException(f"Coding {coding_id} not found")
        return coding

    async def get_debate_codings(
        self,
        debate_id: UUID,
        coder_id: Optional[int] = None,
        persona: Optional[str] = None,
    ) -> List[PersonaCoding]:
        """
        Get all coding records for a debate.

        Args:
            debate_id: Debate session ID
            coder_id: Optional filter by coder
            persona: Optional filter by persona

        Returns:
            List[PersonaCoding]: Coding records ordered by turn_index
        """
        query = select(PersonaCoding).where(PersonaCoding.debate_id == debate_id)

        if coder_id:
            query = query.where(PersonaCoding.coder_id == coder_id)
        if persona:
            query = query.where(PersonaCoding.persona == persona)

        query = query.order_by(PersonaCoding.turn_index)

        result = await self.session.exec(query)
        return result.all()

    # ==================== Update ====================

    async def update_coding(
        self,
        coding_id: UUID,
        data: PersonaCodingUpdate,
        requester_id: int,
    ) -> PersonaCoding:
        """
        Update an existing coding record.

        Only the original coder can update their coding.

        Args:
            coding_id: Coding record ID
            data: Update data
            requester_id: User making the request

        Returns:
            PersonaCoding: Updated coding

        Raises:
            NotFoundException: If coding not found
            ForbiddenException: If requester is not the original coder
        """
        coding = await self.get_coding_by_id(coding_id)

        if coding.coder_id != requester_id:
            raise ForbiddenException("You can only update your own coding records")

        # Apply updates
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(coding, field, value)

        coding.updated_at = datetime.now(timezone.utc)
        self.session.add(coding)
        await self.session.commit()
        await self.session.refresh(coding)

        logger.info("coding_updated", coding_id=str(coding_id))
        return coding

    # ==================== Delete ====================

    async def delete_coding(
        self,
        coding_id: UUID,
        requester_id: int,
    ) -> None:
        """
        Delete a coding record.

        Only the original coder can delete their coding.

        Args:
            coding_id: Coding record ID
            requester_id: User making the request

        Raises:
            NotFoundException: If coding not found
            ForbiddenException: If requester is not the original coder
        """
        coding = await self.get_coding_by_id(coding_id)

        if coding.coder_id != requester_id:
            raise ForbiddenException("You can only delete your own coding records")

        await self.session.delete(coding)
        await self.session.commit()

        logger.info("coding_deleted", coding_id=str(coding_id))

    # ==================== RQ2 Summary Generation ====================

    async def generate_debate_summary(
        self,
        debate_id: UUID,
    ) -> PersonaCodingSummary:
        """
        Generate RQ2 summary for a debate session.

        Aggregates all PersonaCoding records for the debate into
        per-persona consistency metrics.

        Args:
            debate_id: Debate session ID

        Returns:
            PersonaCodingSummary: RQ2 metrics for thesis analysis

        Raises:
            NotFoundException: If debate not found
            BadRequestException: If insufficient codings (< 20% of turns)
        """
        log = logger.bind(
            operation="generate_debate_summary",
            debate_id=str(debate_id),
        )

        # Verify debate exists and get total turns
        debate = await self.session.get(DebateSession, debate_id)
        if not debate:
            raise NotFoundException(f"Debate {debate_id} not found")

        total_turns = debate.total_turns
        if not total_turns or total_turns == 0:
            raise BadRequestException("Debate has no turns")

        # Fetch all codings for this debate
        codings = await self.get_debate_codings(debate_id)

        if not codings:
            raise BadRequestException("No coding records found for this debate")

        coding_coverage = len(codings) / total_turns

        if coding_coverage < 0.20:
            logger.warning(
                "insufficient_coding_coverage",
                coverage=coding_coverage,
                codings=len(codings),
                total_turns=total_turns,
            )

        # Group by persona
        persona_codings = {
            AgentPersona.LEGACY_KEEPER: [],
            AgentPersona.INNOVATOR: [],
            AgentPersona.MEDIATOR: [],
        }

        for coding in codings:
            try:
                persona_enum = AgentPersona(coding.persona)
                if persona_enum in persona_codings:
                    persona_codings[persona_enum].append(coding)
            except ValueError:
                logger.warning("unknown_persona_in_coding", persona=coding.persona)

        # Calculate per-persona breakdowns
        legacy_keeper = self._calculate_persona_breakdown(
            persona="legacy_keeper",
            codings=persona_codings[AgentPersona.LEGACY_KEEPER],
        )
        innovator = self._calculate_persona_breakdown(
            persona="innovator",
            codings=persona_codings[AgentPersona.INNOVATOR],
        )
        mediator = self._calculate_persona_breakdown(
            persona="mediator",
            codings=persona_codings[AgentPersona.MEDIATOR],
        )

        # Calculate overall metrics
        all_codings = codings
        fully_consistent = sum(
            1 for c in all_codings if c.in_character == InCharacterRating.YES
        )
        partially_consistent = sum(
            1 for c in all_codings if c.in_character == InCharacterRating.PARTIAL
        )
        has_hallucination = sum(
            1 for c in all_codings if c.hallucination != HallucinationRating.NONE
        )
        bias_aligned = sum(1 for c in all_codings if c.bias_alignment)

        overall_consistency = (fully_consistent + partially_consistent) / len(
            all_codings
        )
        overall_hallucination_rate = has_hallucination / len(all_codings)
        overall_bias_alignment_rate = bias_aligned / len(all_codings)

        # Get unique coder IDs
        coder_ids = list(set(c.coder_id for c in all_codings))

        # Total coding time
        total_coding_time = sum(
            c.coding_duration_seconds for c in all_codings if c.coding_duration_seconds
        )

        summary = PersonaCodingSummary(
            debate_id=debate_id,
            total_turns_in_debate=total_turns,
            turns_coded=len(codings),
            coding_coverage=coding_coverage,
            legacy_keeper=legacy_keeper,
            innovator=innovator,
            mediator=mediator,
            overall_consistency_rate=round(overall_consistency, 3),
            overall_hallucination_rate=round(overall_hallucination_rate, 3),
            overall_bias_alignment_rate=round(overall_bias_alignment_rate, 3),
            coder_ids=coder_ids,
            total_coding_time_seconds=total_coding_time if total_coding_time else None,
        )

        log.info(
            "debate_summary_generated",
            turns_coded=len(codings),
            coverage=round(coding_coverage, 2),
            overall_consistency=round(overall_consistency, 2),
        )

        return summary

    async def write_consistency_to_debate(
        self,
        debate_id: UUID,
    ) -> DebateSession:
        """
        Write RQ2 consistency scores back to DebateSession.

        This closes the loop: manual codings → aggregated scores → debate record.
        Frontend can then display consistency scores alongside debates.

        Args:
            debate_id: Debate session ID

        Returns:
            DebateSession: Updated debate with consistency scores

        Raises:
            NotFoundException: If debate not found
        """
        summary = await self.generate_debate_summary(debate_id)
        debate = await self.session.get(DebateSession, debate_id)

        if not debate:
            raise NotFoundException(f"Debate {debate_id} not found")

        # Write scores from summary
        scores = summary.to_consistency_update
        debate.legacy_keeper_consistency = scores["legacy_keeper_consistency"]
        debate.innovator_consistency = scores["innovator_consistency"]
        debate.mediator_consistency = scores["mediator_consistency"]

        self.session.add(debate)
        await self.session.commit()
        await self.session.refresh(debate)

        logger.info("consistency_scores_written_to_debate", debate_id=str(debate_id))
        return debate

    # ==================== Export ====================

    async def export_debate_codings(
        self,
        debate_id: UUID,
    ) -> List[dict]:
        """
        Export coding records for statistical analysis.

        Returns flat records ready for CSV/SPSS export.

        Args:
            debate_id: Debate session ID

        Returns:
            List[dict]: Flattened export rows
        """
        codings = await self.get_debate_codings(debate_id)

        export_rows = []
        for coding in codings:
            export_rows.append(
                {
                    "debate_id": str(coding.debate_id),
                    "turn_index": coding.turn_index,
                    "persona": coding.persona,
                    "in_character": coding.in_character.value,
                    "consistency_score": coding.consistency_score,
                    "hallucination": coding.hallucination.value,
                    "hallucination_score": coding.hallucination_score,
                    "bias_alignment": coding.bias_alignment,
                    "quality_attribute_count": coding.quality_attribute_count,
                    "coder_id": coding.coder_id,
                    "coding_duration_seconds": coding.coding_duration_seconds,
                    "created_at": coding.created_at.isoformat(),
                }
            )

        logger.info("codings_exported", debate_id=str(debate_id), rows=len(export_rows))
        return export_rows

    # ==================== Private Helpers ====================

    async def _get_existing_coding(
        self,
        debate_id: UUID,
        turn_index: int,
        coder_id: int,
    ) -> Optional[PersonaCoding]:
        """Check if a coding already exists for this turn/coder combination."""
        result = await self.session.exec(
            select(PersonaCoding).where(
                PersonaCoding.debate_id == debate_id,
                PersonaCoding.turn_index == turn_index,
                PersonaCoding.coder_id == coder_id,
            )
        )
        return result.first()

    def _calculate_persona_breakdown(
        self,
        persona: str,
        codings: List[PersonaCoding],
    ) -> PersonaConsistencyBreakdown:
        """Calculate consistency metrics for a single persona."""
        if not codings:
            return PersonaConsistencyBreakdown(
                persona=persona,
                total_turns_coded=0,
                fully_consistent=0,
                partially_consistent=0,
                inconsistent=0,
                mean_consistency_score=0.0,
                hallucination_count=0,
                major_hallucination_count=0,
                bias_aligned_count=0,
                top_quality_attributes=[],
            )

        fully_consistent = sum(
            1 for c in codings if c.in_character == InCharacterRating.YES
        )
        partially_consistent = sum(
            1 for c in codings if c.in_character == InCharacterRating.PARTIAL
        )
        inconsistent = sum(1 for c in codings if c.in_character == InCharacterRating.NO)

        mean_score = sum(c.consistency_score for c in codings) / len(codings)

        hallucination_count = sum(
            1 for c in codings if c.hallucination != HallucinationRating.NONE
        )
        major_hallucination_count = sum(
            1 for c in codings if c.hallucination == HallucinationRating.MAJOR
        )

        bias_aligned_count = sum(1 for c in codings if c.bias_alignment)

        # Extract top QA attributes
        qa_counter = {}
        for coding in codings:
            for qa in coding.quality_attributes or []:
                qa_counter[qa] = qa_counter.get(qa, 0) + 1

        top_qa = sorted(qa_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        top_quality_attributes = [qa for qa, _ in top_qa]

        return PersonaConsistencyBreakdown(
            persona=persona,
            total_turns_coded=len(codings),
            fully_consistent=fully_consistent,
            partially_consistent=partially_consistent,
            inconsistent=inconsistent,
            mean_consistency_score=round(mean_score, 3),
            hallucination_count=hallucination_count,
            major_hallucination_count=major_hallucination_count,
            bias_aligned_count=bias_aligned_count,
            top_quality_attributes=top_quality_attributes,
        )
