"""
Thesis metrics endpoints for research data collection and analysis.

Provides:
    - RQ2: Persona coding workflow (manual validation)
    - Submit/update/export persona codings
    - Generate RQ2 summary reports per debate
    - Export all thesis data (debates, questionnaires, codings)
    - Metrics aggregation for Chapter 5

Research Questions:
    - RQ2: Do AI personas maintain consistent character throughout debates?

Workflow:
    1. Researcher samples debate turns (20%)
    2. Manually codes each turn (in-character rating, QA mentions, bias alignment)
    3. Submits codings via API
    4. Generates summary metrics
    5. Exports data for statistical analysis
"""

from app.models.questionnaire import QuestionnaireResponse
from app.models.participant import Participant
import structlog
import csv
import io
import zipfile
import random
from datetime import datetime, timezone
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.exceptions import BadRequestException
from app.models.user import User
from app.models.debate import DebateSession
from app.models.persona_coding import PersonaCoding
from app.schemas.persona_coding import (
    PersonaCodingCreate,
    PersonaCodingRead,
    PersonaCodingUpdate,
    PersonaCodingSummary,
)
from app.services.persona_coding_service import PersonaCodingService
from app.research_tools.thematic_analysis import ThematicAnalysisService

logger = structlog.get_logger()
router = APIRouter()


# ==================== Persona Coding (RQ2) ====================


@router.post("/persona-coding", response_model=PersonaCodingRead, status_code=201)
async def submit_persona_coding(
    coding_data: PersonaCodingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Submit a manual persona coding record.

    Used by researchers to validate RQ2 (persona consistency).
    The coder_id is automatically set to the authenticated user's ID.

    Args:
        coding_data: Coding record (debate_id, turn_index, ratings)

    Returns:
        PersonaCodingRead: Submitted coding

    Raises:
        BadRequestException: If duplicate coding or validation fails
    """
    log = logger.bind(
        operation="submit_coding",
        debate_id=str(coding_data.debate_id),
        turn_index=coding_data.turn_index,
    )

    # Auto-inject coder_id from authenticated user
    coding_data = coding_data.model_copy(update={"coder_id": current_user.id})

    persona_coding_service = PersonaCodingService(session)

    try:
        coding = await persona_coding_service.submit_coding(coding_data)
        log.info("coding_submitted", coding_id=str(coding.id))
        return coding

    except BadRequestException:
        raise
    except Exception as e:
        log.error("coding_submission_failed", error=str(e))
        raise BadRequestException(f"Coding submission failed: {str(e)}")


@router.get(
    "/persona-coding/debate/{debate_id}", response_model=List[PersonaCodingRead]
)
async def get_debate_codings(
    debate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    coder_id: int | None = Query(default=None),
):
    """
    Get all persona codings for a debate.

    Args:
        debate_id: Debate session UUID
        coder_id: Optional filter by coder

    Returns:
        List[PersonaCodingRead]: Coding records
    """
    persona_coding_service = PersonaCodingService(session)

    codings = await persona_coding_service.get_debate_codings(
        debate_id=debate_id,
        coder_id=coder_id,
    )

    return codings


@router.patch("/persona-coding/{coding_id}", response_model=PersonaCodingRead)
async def update_persona_coding(
    coding_id: UUID,
    coding_update: PersonaCodingUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Update an existing persona coding.

    Only the original coder can update their coding.

    Args:
        coding_id: Coding record UUID
        coding_update: Fields to update

    Returns:
        PersonaCodingRead: Updated coding

    Raises:
        NotFoundException: If coding not found
        ForbiddenException: If user is not the original coder
    """
    persona_coding_service = PersonaCodingService(session)

    coding = await persona_coding_service.update_coding(
        coding_id=coding_id,
        data=coding_update,
        requester_id=current_user.id,
    )

    logger.info("coding_updated", coding_id=str(coding_id))
    return coding


@router.delete("/persona-coding/{coding_id}", status_code=204)
async def delete_persona_coding(
    coding_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a persona coding.

    Only the original coder can delete their coding.

    Args:
        coding_id: Coding record UUID

    Returns:
        None (204 No Content)

    Raises:
        NotFoundException: If coding not found
        ForbiddenException: If user is not the original coder
    """
    persona_coding_service = PersonaCodingService(session)

    await persona_coding_service.delete_coding(
        coding_id=coding_id,
        requester_id=current_user.id,
    )

    logger.info("coding_deleted", coding_id=str(coding_id))
    return None


# ==================== RQ2 Summary Reports ====================


@router.get(
    "/persona-coding/debate/{debate_id}/summary", response_model=PersonaCodingSummary
)
async def get_debate_coding_summary(
    debate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Generate RQ2 summary for a debate.

    Aggregates all PersonaCoding records into per-persona consistency metrics.

    Args:
        debate_id: Debate session UUID

    Returns:
        PersonaCodingSummary: RQ2 metrics

    Raises:
        NotFoundException: If debate not found
        BadRequestException: If insufficient codings (< 20% of turns)
    """
    persona_coding_service = PersonaCodingService(session)

    summary = await persona_coding_service.generate_debate_summary(debate_id)

    logger.info(
        "coding_summary_generated",
        debate_id=str(debate_id),
        turns_coded=summary.turns_coded,
    )

    return summary


@router.post("/persona-coding/debate/{debate_id}/write-scores")
async def write_consistency_scores(
    debate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Write RQ2 consistency scores to DebateSession.

    Closes the loop: manual codings → aggregated scores → debate record.

    Args:
        debate_id: Debate session UUID

    Returns:
        dict: Success message with scores

    Raises:
        NotFoundException: If debate not found
        BadRequestException: If insufficient codings
    """
    persona_coding_service = PersonaCodingService(session)

    debate = await persona_coding_service.write_consistency_to_debate(debate_id)

    logger.info("consistency_scores_written", debate_id=str(debate_id))

    return {
        "success": True,
        "debate_id": str(debate_id),
        "scores": {
            "legacy_keeper": debate.legacy_keeper_consistency,
            "innovator": debate.innovator_consistency,
            "mediator": debate.mediator_consistency,
        },
    }


# ==================== Data Export ====================


@router.post("/thematic-analysis")
async def run_thematic_analysis(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    field: str = Query(
        default="what_worked_well",
        description="Exit survey field to analyse: what_worked_well | what_could_improve | additional_comments",
    ),
):
    """
    Run LLM-assisted thematic analysis on exit survey open-ended responses.

    Pulls free-text answers from the specified exit survey field, passes them
    to ThematicAnalysisService, and returns a structured list of emergent themes
    with example quotes and frequency counts.

    This is a post-study researcher tool (Section 3.4.2). Results should be
    used as an initial codebook and refined manually before reporting.

    Args:
        field: Which exit survey free-text column to analyse.

    Returns:
        dict with 'field', 'response_count', and 'themes' list.

    Raises:
        BadRequestException: If field name is invalid or no responses found.
    """
    valid_fields = {"what_worked_well", "what_could_improve", "additional_comments"}
    if field not in valid_fields:
        raise BadRequestException(
            f"Invalid field '{field}'. Must be one of: {', '.join(sorted(valid_fields))}"
        )

    from sqlmodel import select
    from app.models.exit_survey import ExitSurvey

    result = await session.exec(select(ExitSurvey))
    all_surveys = result.all()

    responses = [
        getattr(row, field)
        for row in all_surveys
        if getattr(row, field, None) and str(getattr(row, field)).strip()
    ]

    if not responses:
        raise BadRequestException(f"No non-empty responses found for field '{field}'.")

    logger.info(
        "thematic_analysis_started",
        field=field,
        response_count=len(responses),
        user_id=current_user.id,
    )

    themes_result = await ThematicAnalysisService().extract_themes(responses)

    logger.info(
        "thematic_analysis_complete",
        field=field,
        theme_count=len(themes_result.get("themes", [])),
    )

    return {
        "field": field,
        "response_count": len(responses),
        **themes_result,
    }


# ==================== Persona Verification Sample (RQ2 Coding Workflow) ====================


@router.get("/persona-coding/verification-sample")
async def get_verification_sample(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    batch_size: int = Query(default=10, ge=1, le=50),
) -> list:
    """
    Return a random 20% sample of debate turns that have not yet been coded.

    The frontend persona coding tool calls this to populate its queue.
    Each item contains: debate_id, turn_index, persona, response, timestamp.

    Returns:
        List of uncoded transcript turns (up to batch_size).
    """
    log = logger.bind(operation="get_verification_sample", batch_size=batch_size)

    # Fetch all completed debate sessions
    debates_result = await session.exec(select(DebateSession))
    debates = debates_result.all()

    if not debates:
        return []

    # Collect all (debate_id, turn_index, persona) combos that are already coded
    codings_result = await session.exec(select(PersonaCoding))
    already_coded = {
        (str(c.debate_id), c.turn_index, c.persona) for c in codings_result.all()
    }

    # Build list of uncoded turns from debate histories
    uncoded_turns = []
    for debate in debates:
        history = debate.debate_history or []
        for turn in history:
            key = (str(debate.id), turn.get("turn_number", 0), turn.get("persona", ""))
            if key not in already_coded and turn.get("response"):
                uncoded_turns.append(
                    {
                        "debate_id": str(debate.id),
                        "turn_index": turn.get("turn_number", 0),
                        "persona": turn.get("persona", "unknown"),
                        "response": turn.get("response", ""),
                        "timestamp": turn.get("timestamp", ""),
                    }
                )

    if not uncoded_turns:
        log.info("no_uncoded_turns_found")
        return []

    # Sample 20% or up to batch_size
    sample_size = min(batch_size, max(1, len(uncoded_turns) // 5))
    sample = random.sample(uncoded_turns, min(sample_size, len(uncoded_turns)))

    log.info(
        "verification_sample_returned",
        sample_size=len(sample),
        total_uncoded=len(uncoded_turns),
    )
    return sample


@router.get("/export/persona-codings")
async def export_persona_codings(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    debate_id: UUID | None = Query(default=None),
):
    """
    Export persona coding data for statistical analysis.

    Args:
        debate_id: Optional filter by debate

    Returns:
        CSV file with coding records
    """
    persona_coding_service = PersonaCodingService(session)

    if debate_id:
        export_rows = await persona_coding_service.export_debate_codings(debate_id)
    else:
        # Export all codings (across all debates)
        from sqlmodel import select
        from app.models.persona_coding import PersonaCoding

        result = await session.exec(select(PersonaCoding))
        all_codings = result.all()

        export_rows = []
        for coding in all_codings:
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

    # Generate CSV
    csv_buffer = io.StringIO()
    if export_rows:
        writer = csv.DictWriter(csv_buffer, fieldnames=export_rows[0].keys())
        writer.writeheader()
        writer.writerows(export_rows)

    logger.info("persona_codings_exported", rows=len(export_rows))

    return Response(
        content=csv_buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="persona_codings_{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv"'
        },
    )


@router.get("/export/thesis-data")
async def export_all_thesis_data(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Export complete thesis dataset as ZIP file.

    Includes:
    - debates.csv (RQ3: consensus efficiency)
    - questionnaires.csv (RQ1: trust scores)
    - persona_codings.csv (RQ2: persona consistency)
    - README.txt

    Returns:
        ZIP file for SPSS/R analysis
    """
    log = logger.bind(operation="export_thesis_data")

    debates_result = await session.exec(select(DebateSession))
    debates = debates_result.all()

    debates_csv = io.StringIO()
    debates_writer = csv.writer(debates_csv)
    debates_writer.writerow(
        [
            "debate_id",
            "proposal_id",
            "duration_seconds",
            "total_turns",
            "consensus_reached",
            "conflict_density",
            "legacy_keeper_consistency",
            "innovator_consistency",
            "mediator_consistency",
            "started_at",
        ]
    )
    for d in debates:
        debates_writer.writerow(
            [
                str(d.id),
                d.proposal_id,
                d.duration_seconds,
                d.total_turns,
                d.consensus_reached,
                d.conflict_density,
                d.legacy_keeper_consistency,
                d.innovator_consistency,
                d.mediator_consistency,
                d.started_at.isoformat() if d.started_at else None,
            ]
        )

    # 2. Questionnaires CSV
    q_result = await session.exec(
        select(QuestionnaireResponse).where(QuestionnaireResponse.is_valid)
    )
    questionnaire_rows = q_result.all()

    questionnaires_csv = io.StringIO()
    q_writer = csv.writer(questionnaires_csv)
    q_writer.writerow(
        [
            "participant_id",
            "scenario_id",
            "condition",
            "condition_order",
            "trust_overall",
            "risk_awareness",
            "technical_soundness",
            "balance",
            "actionability",
            "completeness",
            "mean_score",
            "time_to_complete_seconds",
            "order_in_session",
            "session_id",
            "submitted_at",
        ]
    )
    for row in questionnaire_rows:
        q_writer.writerow(
            [
                row.participant_id,
                row.scenario_id,
                row.condition.value,
                row.condition_order,
                row.trust_overall,
                row.risk_awareness,
                row.technical_soundness,
                row.balance,
                row.actionability,
                row.completeness,
                row.mean_score,
                row.time_to_complete_seconds,
                row.order_in_session,
                row.session_id,
                row.submitted_at.isoformat() if row.submitted_at else None,
            ]
        )

    codings_result = await session.exec(select(PersonaCoding))
    codings = codings_result.all()

    codings_csv = io.StringIO()
    c_writer = csv.writer(codings_csv)
    c_writer.writerow(
        [
            "debate_id",
            "turn_index",
            "persona",
            "in_character",
            "consistency_score",
            "hallucination",
            "bias_alignment",
            "quality_attribute_count",
            "coder_id",
        ]
    )
    for c in codings:
        c_writer.writerow(
            [
                str(c.debate_id),
                c.turn_index,
                c.persona,
                c.in_character.value,
                c.consistency_score,
                c.hallucination.value,
                c.bias_alignment,
                c.quality_attribute_count,
                c.coder_id,
            ]
        )

    # 4. Baseline variations CSV (Condition A RQ3 timing — mirrors debates.csv columns)
    from app.models.proposal import ProposalVariation, AgentPersona

    baseline_result = await session.exec(
        select(ProposalVariation).where(
            ProposalVariation.agent_persona == AgentPersona.BASELINE
        )
    )
    baseline_variations = baseline_result.all()

    baseline_csv = io.StringIO()
    b_writer = csv.writer(baseline_csv)
    b_writer.writerow(
        [
            "variation_id",
            "proposal_id",
            "condition",
            "generation_seconds",
            "created_at",
        ]
    )
    for bv in baseline_variations:
        b_writer.writerow(
            [
                bv.id,
                bv.proposal_id,
                "baseline",
                bv.generation_seconds,
                bv.created_at.isoformat() if bv.created_at else None,
            ]
        )

    # 5. Exit surveys CSV — with resolved preferred_system_actual
    from app.models.exit_survey import ExitSurvey

    exit_result = await session.exec(select(ExitSurvey))
    exit_surveys = exit_result.all()

    # Build a lookup of participant_id -> assigned_condition_order
    participants_result = await session.exec(select(Participant))
    participants_map = {
        p.id: p.assigned_condition_order for p in participants_result.all()
    }

    exit_csv = io.StringIO()
    e_writer = csv.writer(exit_csv)
    e_writer.writerow(
        [
            "participant_id",
            "condition_order",
            "preferred_system_raw",  # "first" or "second" as the participant saw it
            "preferred_system_actual",  # resolved: "baseline", "multiagent", "no_preference", "not_sure"
            "preference_reasoning",
            "interface_rating",
            "experienced_fatigue",
            "submitted_at",
        ]
    )
    for es in exit_surveys:
        cond_order = participants_map.get(es.participant_id, None)
        raw = (
            es.preferred_system.value
        )  # "first", "second", "no_preference", "not_sure"

        # Resolve "first"/"second" to the actual condition label
        if raw == "first":
            actual = "baseline" if cond_order == "baseline_first" else "multiagent"
        elif raw == "second":
            actual = "multiagent" if cond_order == "baseline_first" else "baseline"
        else:
            actual = raw  # "no_preference" or "not_sure" — pass through unchanged

        e_writer.writerow(
            [
                es.participant_id,
                cond_order,
                raw,
                actual,
                es.preference_reasoning,
                es.interface_rating,
                es.experienced_fatigue.value,
                es.submitted_at.isoformat() if es.submitted_at else None,
            ]
        )

    # 6. Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("debates.csv", debates_csv.getvalue())
        zip_file.writestr("baseline_variations.csv", baseline_csv.getvalue())
        zip_file.writestr("questionnaires.csv", questionnaires_csv.getvalue())
        zip_file.writestr("exit_surveys.csv", exit_csv.getvalue())
        zip_file.writestr("persona_codings.csv", codings_csv.getvalue())
        zip_file.writestr(
            "README.txt",
            f"""Simurgh AI - Thesis Data Export
Generated: {datetime.now(timezone.utc).isoformat()}

Files:
- debates.csv: RQ3 consensus efficiency metrics (Condition B — multi-agent)
    Columns: debate_id, proposal_id, duration_seconds, total_turns,
            consensus_reached, conflict_density,
            legacy_keeper_consistency, innovator_consistency, mediator_consistency,
            started_at
- baseline_variations.csv: RQ3 generation timing (Condition A — single-agent)
    Columns: variation_id, proposal_id, condition, generation_seconds, created_at
    NOTE: generation_seconds is NULL for rows generated before this field was added.
- questionnaires.csv: RQ1 trust and quality ratings (both conditions)
- persona_codings.csv: RQ2 manual persona consistency validation

RQ3 Efficiency Comparison:
    debates.duration_seconds      → Condition B wall-clock time
    baseline_variations.generation_seconds → Condition A wall-clock time
    Both fields measure elapsed seconds from first API call to saved record.

Experimental Conditions:
- Condition A: Baseline (single-agent)
- Condition B: Multi-Agent Council (3 personas)

For statistical analysis in SPSS/R/Python.
""",
        )

    zip_buffer.seek(0)

    log.info(
        "thesis_data_exported",
        debates=len(debates),
        questionnaires=len(questionnaire_rows),
        codings=len(codings),
        baseline_variations=len(baseline_variations),
    )

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="thesis_data_{datetime.now(timezone.utc).strftime("%Y%m%d")}.zip"'
        },
    )
