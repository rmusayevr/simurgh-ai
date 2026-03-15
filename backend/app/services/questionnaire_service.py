"""
Questionnaire service for thesis RQ1/RQ3 evaluation.

Handles participant evaluation questionnaires for A/B testing:
    - RQ1: Trust and quality perception (baseline vs multi-agent)
    - RQ3: Consensus efficiency and decision confidence

Questionnaire structure:
    - 7-point Likert scales (1=Strongly Disagree, 7=Strongly Agree)
    - Separate questions for baseline and multi-agent conditions
    - Open-ended feedback fields
    - Participant demographics
    - Session metadata (time to complete, condition order)

Workflow:
    1. Participant reviews baseline proposal → fills baseline questions
    2. Participant reviews multi-agent proposal → fills multi-agent questions
    3. Service validates responses (Likert 1-7, required fields)
    4. Calculate summary statistics for thesis Chapter 5
    5. Export to CSV/SPSS for statistical analysis
"""

import structlog
from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.questionnaire import ExperimentCondition, QuestionnaireResponse
from app.schemas.questionnaire import (
    QuestionnaireCreate,
    QuestionnaireUpdate,
    QuestionnaireExportRow,
    QuestionnaireExportSummary,
)
from app.core.exceptions import (
    NotFoundException,
)

logger = structlog.get_logger()


class QuestionnaireService:
    """
    Service for managing thesis evaluation questionnaires.

    Collects participant ratings for RQ1 (trust/quality) and
    RQ3 (consensus efficiency) analysis.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Submit Response ====================

    async def submit_response(
        self,
        data: QuestionnaireCreate,
    ) -> QuestionnaireResponse:
        """
        Submit a questionnaire response.

        Validates Likert scores and required fields based on condition.

        Args:
            data: Questionnaire response data

        Returns:
            QuestionnaireResponse: Created response record

        Raises:
            BadRequestException: If validation fails
        """
        log = logger.bind(
            operation="submit_questionnaire",
            participant_id=data.participant_id,
            scenario_id=data.scenario_id,
        )

        # Create response record
        response = QuestionnaireResponse(
            participant_id=data.participant_id,
            scenario_id=data.scenario_id,
            condition=data.condition,
            # Likert Scales (1-7)
            trust_overall=data.trust_overall,
            risk_awareness=data.risk_awareness,
            technical_soundness=data.technical_soundness,
            balance=data.balance,
            actionability=data.actionability,
            completeness=data.completeness,
            # Open-ended
            strengths=data.strengths,
            concerns=data.concerns,
            trust_reasoning=data.trust_reasoning,
            # Multi-agent only
            persona_consistency=data.persona_consistency,
            debate_value=data.debate_value,
            most_convincing_persona=data.most_convincing_persona,
            # Metadata
            time_to_complete_seconds=data.time_to_complete_seconds,
            order_in_session=data.order_in_session,
            session_id=data.session_id,
            condition_order=data.condition_order,
            is_valid=True,  # Default to valid, can be flagged later
        )

        self.session.add(response)
        await self.session.commit()
        await self.session.refresh(response)

        log.info(
            "questionnaire_submitted",
            response_id=response.id,
            condition=response.condition.value,
            mean_score=response.mean_score,
        )

        return response

    # ==================== Read ====================

    async def get_response_by_id(
        self,
        response_id: int,
    ) -> QuestionnaireResponse:
        """
        Get a questionnaire response by ID.

        Raises:
            NotFoundException: If response not found
        """
        response = await self.session.get(QuestionnaireResponse, response_id)
        if not response:
            raise NotFoundException(f"Questionnaire response {response_id} not found")
        return response

    async def get_all_responses(
        self,
        valid_only: bool = True,
    ) -> List[QuestionnaireResponse]:
        """
        Get all questionnaire responses, optionally filtered by validity.

        Args:
            valid_only: Only return valid (non-flagged) responses

        Returns:
            List[QuestionnaireResponse]: All matching responses
        """
        query = select(QuestionnaireResponse)
        if valid_only:
            query = query.where(QuestionnaireResponse.is_valid)
        result = await self.session.exec(query)
        return result.all()

    async def get_scenario_responses(
        self,
        scenario_id: int,
        valid_only: bool = True,
    ) -> List[QuestionnaireResponse]:
        """
        Get all questionnaire responses for a scenario.

        Args:
            scenario_id: Target scenario ID (1-4)
            valid_only: Only return valid (non-flagged) responses

        Returns:
            List[QuestionnaireResponse]: Questionnaire responses
        """
        query = select(QuestionnaireResponse).where(
            QuestionnaireResponse.scenario_id == scenario_id
        )

        if valid_only:
            query = query.where(QuestionnaireResponse.is_valid)

        query = query.order_by(QuestionnaireResponse.submitted_at)

        result = await self.session.exec(query)
        return result.all()

    async def get_participant_responses(
        self,
        participant_id: int,
    ) -> List[QuestionnaireResponse]:
        """
        Get all responses from a specific participant.

        Args:
            participant_id: Participant identifier

        Returns:
            List[QuestionnaireResponse]: Participant's responses
        """
        result = await self.session.exec(
            select(QuestionnaireResponse)
            .where(QuestionnaireResponse.participant_id == participant_id)
            .order_by(QuestionnaireResponse.submitted_at)
        )
        return result.all()

    # ==================== Update ====================

    async def update_response(
        self,
        response_id: int,
        data: QuestionnaireUpdate,
    ) -> QuestionnaireResponse:
        """
        Update a questionnaire response.

        Typically used to flag invalid responses or update metadata.

        Args:
            response_id: Response ID
            data: Update data

        Returns:
            QuestionnaireResponse: Updated response

        Raises:
            NotFoundException: If response not found
        """
        response = await self.get_response_by_id(response_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(response, field, value)

        self.session.add(response)
        await self.session.commit()
        await self.session.refresh(response)

        logger.info("questionnaire_updated", response_id=response_id)
        return response

    async def flag_invalid(
        self,
        response_id: int,
        reason: str,
    ) -> QuestionnaireResponse:
        """
        Flag a response as invalid.

        Used to exclude incomplete, suspicious, or low-quality responses
        from statistical analysis.

        Args:
            response_id: Response ID to flag
            reason: Reason for invalidation

        Returns:
            QuestionnaireResponse: Flagged response

        Raises:
            NotFoundException: If response not found
        """
        response = await self.get_response_by_id(response_id)

        response.is_valid = False
        response.quality_note = reason

        self.session.add(response)
        await self.session.commit()
        await self.session.refresh(response)

        logger.info(
            "questionnaire_flagged_invalid",
            response_id=response_id,
            reason=reason,
        )

        return response

    # ==================== Summary Statistics ====================

    async def calculate_summary_statistics(
        self,
        scenario_id: Optional[int] = None,
        valid_only: bool = True,
    ) -> dict:
        """
        Calculate summary statistics for thesis analysis.

        Computes mean scores, standard deviations, and sample sizes
        for RQ1 metrics.

        Args:
            scenario_id: Optional filter by scenario
            valid_only: Only include valid responses

        Returns:
            dict: Summary statistics
        """
        log = logger.bind(
            operation="calculate_summary",
            scenario_id=scenario_id,
        )

        # Build query
        query = select(QuestionnaireResponse)

        if scenario_id:
            query = query.where(QuestionnaireResponse.scenario_id == scenario_id)

        if valid_only:
            query = query.where(QuestionnaireResponse.is_valid)

        result = await self.session.exec(query)
        responses = result.all()

        if not responses:
            log.warning("no_responses_found")
            return {
                "total_responses": 0,
                "baseline_n": 0,
                "multiagent_n": 0,
                "baseline_mean_trust": None,
                "multiagent_mean_trust": None,
                "trust_difference": None,
                "baseline_mean_score": None,
                "multiagent_mean_score": None,
                "score_difference": None,
                "cohens_d": None,
            }

        # Separate by condition
        baseline = [r for r in responses if r.condition == ExperimentCondition.BASELINE]
        multiagent = [
            r for r in responses if r.condition == ExperimentCondition.MULTIAGENT
        ]

        # Calculate means (using trust_overall as primary metric)
        baseline_trust = (
            sum(r.trust_overall for r in baseline) / len(baseline) if baseline else None
        )
        multiagent_trust = (
            sum(r.trust_overall for r in multiagent) / len(multiagent)
            if multiagent
            else None
        )

        # Calculate mean_score (composite across all 6 Likert items)
        baseline_mean_score = (
            sum(r.mean_score for r in baseline) / len(baseline) if baseline else None
        )
        multiagent_mean_score = (
            sum(r.mean_score for r in multiagent) / len(multiagent)
            if multiagent
            else None
        )

        # Calculate within-subjects effect size (Cohen's d_z) using paired scores.
        # This design is within-subjects (each participant rates both conditions),
        # so d_z = mean(difference scores) / SD(difference scores) is the correct
        # effect size measure — NOT the independent-samples pooled-SD formula.
        effect_size = None
        if (
            baseline_mean_score
            and multiagent_mean_score
            and len(baseline) > 1
            and len(multiagent) > 1
        ):
            import statistics
            from collections import defaultdict

            # Build paired scores by participant_id
            paired: dict = defaultdict(dict)
            for r in responses:
                paired[r.participant_id][r.condition] = r.mean_score

            diff_scores = [
                v[ExperimentCondition.MULTIAGENT] - v[ExperimentCondition.BASELINE]
                for v in paired.values()
                if ExperimentCondition.BASELINE in v
                and ExperimentCondition.MULTIAGENT in v
            ]

            if len(diff_scores) > 1:
                mean_diff = statistics.mean(diff_scores)
                sd_diff = statistics.stdev(diff_scores)
                if sd_diff > 0:
                    effect_size = mean_diff / sd_diff  # Cohen's d_z (within-subjects)

        summary = {
            "total_responses": len(responses),
            "baseline_n": len(baseline),
            "multiagent_n": len(multiagent),
            # RQ1: Trust (single item)
            "baseline_mean_trust": round(baseline_trust, 2) if baseline_trust else None,
            "multiagent_mean_trust": (
                round(multiagent_trust, 2) if multiagent_trust else None
            ),
            "trust_difference": (
                round(multiagent_trust - baseline_trust, 2)
                if baseline_trust and multiagent_trust
                else None
            ),
            # RQ1: Composite score (all 6 items)
            "baseline_mean_score": (
                round(baseline_mean_score, 2) if baseline_mean_score else None
            ),
            "multiagent_mean_score": (
                round(multiagent_mean_score, 2) if multiagent_mean_score else None
            ),
            "score_difference": (
                round(multiagent_mean_score - baseline_mean_score, 2)
                if baseline_mean_score and multiagent_mean_score
                else None
            ),
            # Effect size
            "cohens_d": round(effect_size, 3) if effect_size else None,
        }

        log.info("summary_calculated", total_responses=len(responses))
        return summary

    # ==================== Export ====================

    async def export_all_responses(
        self,
        valid_only: bool = True,
    ) -> QuestionnaireExportSummary:
        """
        Export all questionnaire responses for statistical analysis.

        Returns flat CSV-ready data with summary statistics.

        Args:
            valid_only: Only export valid responses

        Returns:
            QuestionnaireExportSummary: Export data + summary stats
        """
        log = logger.bind(operation="export_responses")

        query = select(QuestionnaireResponse)
        if valid_only:
            query = query.where(QuestionnaireResponse.is_valid)

        query = query.order_by(QuestionnaireResponse.submitted_at)

        result = await self.session.exec(query)
        responses = result.all()

        # Convert to export rows
        export_rows = []
        for r in responses:
            export_rows.append(
                QuestionnaireExportRow(
                    participant_id=r.participant_id,
                    scenario_id=r.scenario_id,
                    condition=r.condition.value,
                    condition_order=r.condition_order,
                    trust_overall=r.trust_overall,
                    risk_awareness=r.risk_awareness,
                    technical_soundness=r.technical_soundness,
                    balance=r.balance,
                    actionability=r.actionability,
                    completeness=r.completeness,
                    mean_score=r.mean_score,
                    time_to_complete_seconds=r.time_to_complete_seconds,
                    order_in_session=r.order_in_session,
                    session_id=r.session_id,
                    is_valid=r.is_valid,
                    submitted_at=r.submitted_at.isoformat(),
                )
            )

        # Calculate summary
        summary = await self.calculate_summary_statistics(valid_only=valid_only)

        # Per-item means for baseline and multiagent
        baseline_responses = [
            r for r in responses if r.condition == ExperimentCondition.BASELINE
        ]
        multiagent_responses = [
            r for r in responses if r.condition == ExperimentCondition.MULTIAGENT
        ]

        def _item_means(group: list) -> dict:
            if not group:
                return {
                    k: 0.0
                    for k in [
                        "trust_overall",
                        "risk_awareness",
                        "technical_soundness",
                        "balance",
                        "actionability",
                        "completeness",
                    ]
                }
            return {
                "trust_overall": round(
                    sum(r.trust_overall for r in group) / len(group), 2
                ),
                "risk_awareness": round(
                    sum(r.risk_awareness for r in group) / len(group), 2
                ),
                "technical_soundness": round(
                    sum(r.technical_soundness for r in group) / len(group), 2
                ),
                "balance": round(sum(r.balance for r in group) / len(group), 2),
                "actionability": round(
                    sum(r.actionability for r in group) / len(group), 2
                ),
                "completeness": round(
                    sum(r.completeness for r in group) / len(group), 2
                ),
            }

        # Count straightlining (all 6 Likert scores identical)
        straightlining_count = sum(
            1
            for r in responses
            if len(
                {
                    r.trust_overall,
                    r.risk_awareness,
                    r.technical_soundness,
                    r.balance,
                    r.actionability,
                    r.completeness,
                }
            )
            == 1
        )

        baseline_trust = summary["baseline_mean_trust"] or 0.0
        multiagent_trust = summary["multiagent_mean_trust"] or 0.0

        export_summary = QuestionnaireExportSummary(
            total_responses=len(responses),
            valid_responses=sum(1 for r in responses if r.is_valid),
            baseline_count=summary.get("baseline_n", 0),
            multiagent_count=summary.get("multiagent_n", 0),
            baseline_mean_trust=baseline_trust,
            multiagent_mean_trust=multiagent_trust,
            mean_difference=round(multiagent_trust - baseline_trust, 2),
            baseline_means=_item_means(baseline_responses),
            multiagent_means=_item_means(multiagent_responses),
            invalid_count=sum(1 for r in responses if not r.is_valid),
            straightlining_detected=straightlining_count,
        )

        log.info(
            "responses_exported",
            total_rows=len(export_rows),
            valid=export_summary.valid_responses,
        )
        return export_summary

    # ==================== Delete ====================

    async def delete_response(
        self,
        response_id: int,
    ) -> None:
        """
        Delete a questionnaire response.

        Args:
            response_id: Response ID to delete

        Raises:
            NotFoundException: If response not found
        """
        response = await self.get_response_by_id(response_id)

        await self.session.delete(response)
        await self.session.commit()

        logger.info("questionnaire_deleted", response_id=response_id)
