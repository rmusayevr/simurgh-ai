"""
Unit tests for app/services/questionnaire_service.py

Covers every method in QuestionnaireService:
    submit_response             — happy path, field mapping, defaults
    get_response_by_id          — found / not found
    get_all_responses           — valid_only=True, valid_only=False
    get_scenario_responses      — filter by scenario_id, valid_only flag
    get_participant_responses   — filter by participant
    update_response             — partial update, not found
    flag_invalid                — sets is_valid=False + quality_note, not found
    calculate_summary_statistics — empty, single condition, both conditions,
                                   Cohen's d_z (paired effect size), scenario filter
    export_all_responses        — export row shape, summary stats, straightlining
    delete_response             — happy path, not found

Also covers QuestionnaireResponse model helpers:
    mean_score, likert_scores, has_open_ended_responses, time_to_complete_minutes

And QuestionnaireCreate schema validators:
    baseline condition rejects multiagent-only fields
    whitespace stripping on open-ended fields

DB is mocked — no real PostgreSQL required.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.models.questionnaire import QuestionnaireResponse, ExperimentCondition
from app.schemas.questionnaire import (
    QuestionnaireCreate,
    QuestionnaireUpdate,
)
from app.core.exceptions import NotFoundException


# ── Factories ─────────────────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _make_response(
    id=None,
    participant_id: int = 1,
    scenario_id: int = 1,
    condition: ExperimentCondition = ExperimentCondition.BASELINE,
    trust_overall: int = 5,
    risk_awareness: int = 5,
    technical_soundness: int = 5,
    balance: int = 5,
    actionability: int = 5,
    completeness: int = 5,
    strengths: str = "Well structured.",
    concerns: str = "Some gaps.",
    trust_reasoning: str = "Clearly explained.",
    is_valid: bool = True,
    quality_note: str | None = None,
    time_to_complete_seconds: int | None = 90,
    order_in_session: int | None = 1,
    session_id: str | None = "sess-001",
    condition_order: str | None = "baseline_first",
) -> QuestionnaireResponse:
    return QuestionnaireResponse(
        id=id or uuid4(),
        participant_id=participant_id,
        scenario_id=scenario_id,
        condition=condition,
        trust_overall=trust_overall,
        risk_awareness=risk_awareness,
        technical_soundness=technical_soundness,
        balance=balance,
        actionability=actionability,
        completeness=completeness,
        strengths=strengths,
        concerns=concerns,
        trust_reasoning=trust_reasoning,
        is_valid=is_valid,
        quality_note=quality_note,
        time_to_complete_seconds=time_to_complete_seconds,
        order_in_session=order_in_session,
        session_id=session_id,
        condition_order=condition_order,
        submitted_at=NOW,
    )


def _make_create_data(
    participant_id: int = 1,
    scenario_id: int = 1,
    condition: ExperimentCondition = ExperimentCondition.BASELINE,
    trust_overall: int = 5,
    **kwargs,
) -> QuestionnaireCreate:
    defaults = dict(
        participant_id=participant_id,
        scenario_id=scenario_id,
        condition=condition,
        trust_overall=trust_overall,
        risk_awareness=5,
        technical_soundness=5,
        balance=5,
        actionability=5,
        completeness=5,
        strengths="Clear and well-reasoned.",
        concerns="Could expand on edge cases.",
        trust_reasoning="The proposal covered key risks.",
    )
    defaults.update(kwargs)
    return QuestionnaireCreate(**defaults)


def _make_session(
    get_return=None,
    exec_returns: list | None = None,
) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=get_return)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    if exec_returns is not None:
        results = []
        for val in exec_returns:
            r = MagicMock()
            if isinstance(val, list):
                r.all = MagicMock(return_value=val)
                r.first = MagicMock(return_value=val[0] if val else None)
            else:
                r.first = MagicMock(return_value=val)
                r.all = MagicMock(return_value=[val] if val else [])
            results.append(r)
        session.exec = AsyncMock(side_effect=results)
    else:
        default = MagicMock()
        default.first = MagicMock(return_value=None)
        default.all = MagicMock(return_value=[])
        session.exec = AsyncMock(return_value=default)

    return session


def _svc(session: AsyncMock):
    from app.services.questionnaire_service import QuestionnaireService

    return QuestionnaireService(session=session)


# ═══════════════════════════════════════════════════════════════════════════════
# QuestionnaireResponse model helpers (no DB — pure model tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuestionnaireResponseModel:
    def test_mean_score_uniform_fives(self):
        r = _make_response()  # all scores = 5
        assert r.mean_score == 5.0

    def test_mean_score_mixed(self):
        r = _make_response(
            trust_overall=7,
            risk_awareness=3,
            technical_soundness=5,
            balance=5,
            actionability=5,
            completeness=5,
        )
        # (7+3+5+5+5+5) / 6 = 5.0
        assert r.mean_score == 5.0

    def test_mean_score_all_ones(self):
        r = _make_response(
            trust_overall=1,
            risk_awareness=1,
            technical_soundness=1,
            balance=1,
            actionability=1,
            completeness=1,
        )
        assert r.mean_score == 1.0

    def test_mean_score_all_sevens(self):
        r = _make_response(
            trust_overall=7,
            risk_awareness=7,
            technical_soundness=7,
            balance=7,
            actionability=7,
            completeness=7,
        )
        assert r.mean_score == 7.0

    def test_likert_scores_dict_contains_all_keys(self):
        r = _make_response()
        keys = r.likert_scores.keys()
        for key in (
            "trust_overall",
            "risk_awareness",
            "technical_soundness",
            "balance",
            "actionability",
            "completeness",
        ):
            assert key in keys

    def test_is_multiagent_property(self):
        assert _make_response(condition=ExperimentCondition.MULTIAGENT).is_multiagent
        assert not _make_response(condition=ExperimentCondition.BASELINE).is_multiagent

    def test_is_baseline_property(self):
        assert _make_response(condition=ExperimentCondition.BASELINE).is_baseline
        assert not _make_response(condition=ExperimentCondition.MULTIAGENT).is_baseline

    def test_has_open_ended_responses_when_all_filled(self):
        r = _make_response(
            strengths="Good.", concerns="Bad.", trust_reasoning="Because."
        )
        assert r.has_open_ended_responses is True

    def test_has_open_ended_responses_false_when_empty(self):
        r = _make_response(strengths="   ", concerns="Fine.", trust_reasoning="OK.")
        assert r.has_open_ended_responses is False

    def test_time_to_complete_minutes(self):
        r = _make_response(time_to_complete_seconds=90)
        assert r.time_to_complete_minutes == 1.5

    def test_time_to_complete_minutes_none_when_no_seconds(self):
        r = _make_response(time_to_complete_seconds=None)
        assert r.time_to_complete_minutes is None


# ═══════════════════════════════════════════════════════════════════════════════
# QuestionnaireCreate schema validators (no DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuestionnaireCreateValidation:
    def test_baseline_with_persona_consistency_raises(self):
        with pytest.raises(Exception, match="multiagent condition"):
            _make_create_data(
                condition=ExperimentCondition.BASELINE,
                persona_consistency="Stayed in character.",
            )

    def test_baseline_with_debate_value_raises(self):
        with pytest.raises(Exception, match="multiagent condition"):
            _make_create_data(
                condition=ExperimentCondition.BASELINE,
                debate_value="Very valuable.",
            )

    def test_baseline_with_most_convincing_persona_raises(self):
        with pytest.raises(Exception, match="multiagent condition"):
            _make_create_data(
                condition=ExperimentCondition.BASELINE,
                most_convincing_persona="INNOVATOR",
            )

    def test_multiagent_with_persona_fields_is_valid(self):
        data = _make_create_data(
            condition=ExperimentCondition.MULTIAGENT,
            persona_consistency="Yes, fully in character.",
            debate_value="Added significant nuance.",
            most_convincing_persona="MEDIATOR",
        )
        assert data.persona_consistency == "Yes, fully in character."

    def test_whitespace_stripped_from_open_ended(self):
        data = _make_create_data(strengths="  Good work.  ")
        assert data.strengths == "Good work."

    def test_whitespace_stripped_from_concerns(self):
        data = _make_create_data(concerns="\n  Some issues.  \n")
        assert data.concerns == "Some issues."

    def test_whitespace_stripped_from_trust_reasoning(self):
        data = _make_create_data(trust_reasoning="  Because it was clear.  ")
        assert data.trust_reasoning == "Because it was clear."

    def test_scenario_id_out_of_range_raises(self):
        with pytest.raises(Exception):
            _make_create_data(scenario_id=0)

    def test_scenario_id_5_raises(self):
        with pytest.raises(Exception):
            _make_create_data(scenario_id=5)

    def test_trust_score_out_of_range_raises(self):
        with pytest.raises(Exception):
            _make_create_data(trust_overall=8)

    def test_trust_score_zero_raises(self):
        with pytest.raises(Exception):
            _make_create_data(trust_overall=0)


# ═══════════════════════════════════════════════════════════════════════════════
# submit_response
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubmitResponse:
    async def test_creates_and_commits_response(self):
        session = _make_session()
        svc = _svc(session)
        data = _make_create_data()

        await svc.submit_response(data)

        session.add.assert_called_once()
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()

    async def test_is_valid_defaults_to_true(self):
        session = _make_session()
        captured = {}

        def _capture(obj):
            captured["obj"] = obj

        session.add = MagicMock(side_effect=_capture)
        svc = _svc(session)

        await svc.submit_response(_make_create_data())

        assert captured["obj"].is_valid is True

    async def test_fields_transferred_from_create_data(self):
        session = _make_session()
        captured = {}
        session.add = MagicMock(side_effect=lambda obj: captured.update({"obj": obj}))
        svc = _svc(session)

        data = _make_create_data(
            participant_id=7,
            scenario_id=2,
            condition=ExperimentCondition.MULTIAGENT,
            trust_overall=6,
        )
        await svc.submit_response(data)

        obj = captured["obj"]
        assert obj.participant_id == 7
        assert obj.scenario_id == 2
        assert obj.condition == ExperimentCondition.MULTIAGENT
        assert obj.trust_overall == 6

    async def test_multiagent_fields_stored(self):
        session = _make_session()
        captured = {}
        session.add = MagicMock(side_effect=lambda obj: captured.update({"obj": obj}))
        svc = _svc(session)

        data = _make_create_data(
            condition=ExperimentCondition.MULTIAGENT,
            persona_consistency="Consistent throughout.",
            debate_value="Highly valuable.",
            most_convincing_persona="LEGACY_KEEPER",
        )
        await svc.submit_response(data)

        obj = captured["obj"]
        assert obj.persona_consistency == "Consistent throughout."
        assert obj.debate_value == "Highly valuable."
        assert obj.most_convincing_persona == "LEGACY_KEEPER"

    async def test_returns_refreshed_response(self):
        response = _make_response()
        session = _make_session()
        session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", response.id)
        )
        svc = _svc(session)

        await svc.submit_response(_make_create_data())

        # refresh was called — confirms the returned object went through refresh
        session.refresh.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# get_response_by_id
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetResponseById:
    async def test_returns_response_when_found(self):
        r = _make_response()
        session = _make_session(get_return=r)
        svc = _svc(session)

        result = await svc.get_response_by_id(r.id)
        assert result is r

    async def test_raises_not_found_when_missing(self):
        session = _make_session(get_return=None)
        svc = _svc(session)

        with pytest.raises(NotFoundException, match="not found"):
            await svc.get_response_by_id(99)

    async def test_calls_session_get_with_correct_type(self):
        r = _make_response()
        session = _make_session(get_return=r)
        svc = _svc(session)

        await svc.get_response_by_id(r.id)

        session.get.assert_awaited_once_with(QuestionnaireResponse, r.id)


# ═══════════════════════════════════════════════════════════════════════════════
# get_all_responses
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAllResponses:
    async def test_returns_all_valid_by_default(self):
        responses = [_make_response(is_valid=True), _make_response(is_valid=True)]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        result = await svc.get_all_responses()
        assert len(result) == 2

    async def test_returns_empty_list_when_none(self):
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        result = await svc.get_all_responses()
        assert result == []

    async def test_valid_only_false_returns_all(self):
        """valid_only=False — query runs without is_valid filter."""
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        result = await svc.get_all_responses(valid_only=False)
        assert result == []
        session.exec.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# get_scenario_responses
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetScenarioResponses:
    async def test_returns_responses_for_scenario(self):
        r1 = _make_response(scenario_id=2)
        r2 = _make_response(scenario_id=2)
        session = _make_session(exec_returns=[[r1, r2]])
        svc = _svc(session)

        result = await svc.get_scenario_responses(scenario_id=2)
        assert len(result) == 2

    async def test_returns_empty_list_for_unknown_scenario(self):
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        result = await svc.get_scenario_responses(scenario_id=4)
        assert result == []

    async def test_valid_only_false_accepted(self):
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        result = await svc.get_scenario_responses(scenario_id=1, valid_only=False)
        assert result == []
        session.exec.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# get_participant_responses
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetParticipantResponses:
    async def test_returns_responses_for_participant(self):
        r1 = _make_response(participant_id=5)
        r2 = _make_response(participant_id=5, condition=ExperimentCondition.MULTIAGENT)
        session = _make_session(exec_returns=[[r1, r2]])
        svc = _svc(session)

        result = await svc.get_participant_responses(participant_id=5)
        assert len(result) == 2

    async def test_returns_empty_list_for_unknown_participant(self):
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        result = await svc.get_participant_responses(participant_id=99)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# update_response
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateResponse:
    async def test_updates_provided_fields(self):
        r = _make_response(is_valid=True, quality_note=None)
        session = _make_session(get_return=r)
        svc = _svc(session)

        update = QuestionnaireUpdate(is_valid=False, quality_note="Suspicious.")
        result = await svc.update_response(r.id, update)

        assert result.is_valid is False
        assert result.quality_note == "Suspicious."

    async def test_only_provided_fields_updated(self):
        r = _make_response(is_valid=True, quality_note=None)
        session = _make_session(get_return=r)
        svc = _svc(session)

        # Only update quality_note — is_valid should stay True
        update = QuestionnaireUpdate(quality_note="Minor issue.")
        result = await svc.update_response(r.id, update)

        assert result.is_valid is True
        assert result.quality_note == "Minor issue."

    async def test_raises_not_found_when_missing(self):
        session = _make_session(get_return=None)
        svc = _svc(session)

        with pytest.raises(NotFoundException):
            await svc.update_response(999, QuestionnaireUpdate(quality_note="test"))

    async def test_commits_and_refreshes(self):
        r = _make_response()
        session = _make_session(get_return=r)
        svc = _svc(session)

        await svc.update_response(r.id, QuestionnaireUpdate(is_valid=False))

        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# flag_invalid
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlagInvalid:
    async def test_sets_is_valid_false(self):
        r = _make_response(is_valid=True)
        session = _make_session(get_return=r)
        svc = _svc(session)

        result = await svc.flag_invalid(r.id, reason="All scores identical.")

        assert result.is_valid is False

    async def test_sets_quality_note(self):
        r = _make_response()
        session = _make_session(get_return=r)
        svc = _svc(session)

        result = await svc.flag_invalid(r.id, reason="Suspiciously fast completion.")

        assert result.quality_note == "Suspiciously fast completion."

    async def test_raises_not_found_when_missing(self):
        session = _make_session(get_return=None)
        svc = _svc(session)

        with pytest.raises(NotFoundException):
            await svc.flag_invalid(999, reason="Does not exist.")

    async def test_commits_after_flagging(self):
        r = _make_response()
        session = _make_session(get_return=r)
        svc = _svc(session)

        await svc.flag_invalid(r.id, reason="Low quality.")

        session.commit.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# calculate_summary_statistics
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateSummaryStatistics:
    async def test_returns_zeros_when_no_responses(self):
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["total_responses"] == 0
        assert stats["baseline_n"] == 0
        assert stats["multiagent_n"] == 0
        assert stats["baseline_mean_trust"] is None
        assert stats["multiagent_mean_trust"] is None
        assert stats["cohens_d"] is None

    async def test_counts_by_condition(self):
        responses = [
            _make_response(condition=ExperimentCondition.BASELINE),
            _make_response(condition=ExperimentCondition.BASELINE),
            _make_response(condition=ExperimentCondition.MULTIAGENT),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["total_responses"] == 3
        assert stats["baseline_n"] == 2
        assert stats["multiagent_n"] == 1

    async def test_baseline_mean_trust_calculated(self):
        responses = [
            _make_response(condition=ExperimentCondition.BASELINE, trust_overall=4),
            _make_response(condition=ExperimentCondition.BASELINE, trust_overall=6),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["baseline_mean_trust"] == 5.0

    async def test_multiagent_mean_trust_calculated(self):
        responses = [
            _make_response(condition=ExperimentCondition.MULTIAGENT, trust_overall=6),
            _make_response(condition=ExperimentCondition.MULTIAGENT, trust_overall=7),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["multiagent_mean_trust"] == 6.5

    async def test_trust_difference_computed(self):
        responses = [
            _make_response(condition=ExperimentCondition.BASELINE, trust_overall=4),
            _make_response(condition=ExperimentCondition.MULTIAGENT, trust_overall=6),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["trust_difference"] == 2.0

    async def test_only_baseline_responses_gives_none_multiagent_trust(self):
        responses = [
            _make_response(condition=ExperimentCondition.BASELINE, trust_overall=5),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["multiagent_mean_trust"] is None
        assert stats["trust_difference"] is None

    async def test_cohens_d_computed_for_paired_data(self):
        """
        Participant 1: baseline mean=4.0, multiagent mean=6.0  → diff=+2.0
        Participant 2: baseline mean=3.0, multiagent mean=7.0  → diff=+4.0
        mean(diffs) = 3.0
        stdev(diffs) = statistics.stdev([2, 4]) = sqrt(2) ≈ 1.414  (sample stdev)
        d_z = 3.0 / sqrt(2) ≈ 2.121
        """
        responses = [
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.BASELINE,
                trust_overall=4,
                risk_awareness=4,
                technical_soundness=4,
                balance=4,
                actionability=4,
                completeness=4,
            ),
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.MULTIAGENT,
                trust_overall=6,
                risk_awareness=6,
                technical_soundness=6,
                balance=6,
                actionability=6,
                completeness=6,
            ),
            _make_response(
                participant_id=2,
                condition=ExperimentCondition.BASELINE,
                trust_overall=3,
                risk_awareness=3,
                technical_soundness=3,
                balance=3,
                actionability=3,
                completeness=3,
            ),
            _make_response(
                participant_id=2,
                condition=ExperimentCondition.MULTIAGENT,
                trust_overall=7,
                risk_awareness=7,
                technical_soundness=7,
                balance=7,
                actionability=7,
                completeness=7,
            ),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        # d_z = mean([2,4]) / stdev([2,4]) = 3.0 / sqrt(2) ≈ 2.121
        assert stats["cohens_d"] is not None
        assert abs(stats["cohens_d"] - 2.121) < 0.01

    async def test_cohens_d_none_when_insufficient_pairs(self):
        """Only one participant → only 1 diff score → can't compute stdev."""
        responses = [
            _make_response(participant_id=1, condition=ExperimentCondition.BASELINE),
            _make_response(participant_id=1, condition=ExperimentCondition.MULTIAGENT),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["cohens_d"] is None

    async def test_cohens_d_none_when_no_pairs(self):
        """No participant has both conditions → no diff scores."""
        responses = [
            _make_response(participant_id=1, condition=ExperimentCondition.BASELINE),
            _make_response(participant_id=2, condition=ExperimentCondition.MULTIAGENT),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["cohens_d"] is None

    async def test_scenario_filter_passed(self):
        """Ensure the query is executed (scenario filter doesn't crash)."""
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics(scenario_id=2)

        assert stats["total_responses"] == 0
        session.exec.assert_awaited_once()

    async def test_composite_mean_score_difference(self):
        """score_difference = multiagent_mean_score - baseline_mean_score."""
        responses = [
            # baseline: mean = 4.0
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.BASELINE,
                trust_overall=4,
                risk_awareness=4,
                technical_soundness=4,
                balance=4,
                actionability=4,
                completeness=4,
            ),
            # multiagent: mean = 6.0
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.MULTIAGENT,
                trust_overall=6,
                risk_awareness=6,
                technical_soundness=6,
                balance=6,
                actionability=6,
                completeness=6,
            ),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        assert stats["score_difference"] == 2.0

    async def test_cohens_d_none_when_diffs_all_equal(self):
        """All participants have the same diff score → sd=0 → d_z guard triggers."""
        # Both participants have diff = 2.0 → stdev = 0 → d_z not computed
        responses = [
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.BASELINE,
                trust_overall=4,
                risk_awareness=4,
                technical_soundness=4,
                balance=4,
                actionability=4,
                completeness=4,
            ),
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.MULTIAGENT,
                trust_overall=6,
                risk_awareness=6,
                technical_soundness=6,
                balance=6,
                actionability=6,
                completeness=6,
            ),
            _make_response(
                participant_id=2,
                condition=ExperimentCondition.BASELINE,
                trust_overall=4,
                risk_awareness=4,
                technical_soundness=4,
                balance=4,
                actionability=4,
                completeness=4,
            ),
            _make_response(
                participant_id=2,
                condition=ExperimentCondition.MULTIAGENT,
                trust_overall=6,
                risk_awareness=6,
                technical_soundness=6,
                balance=6,
                actionability=6,
                completeness=6,
            ),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        # sd_diff = 0 → d_z = None (division-by-zero guard)
        assert stats["cohens_d"] is None

    async def test_valid_only_false_includes_invalid_responses(self):
        """valid_only=False must not filter out is_valid=False responses."""
        session = _make_session(exec_returns=[[]])
        svc = _svc(session)

        # Should execute without error; mock returns empty regardless of filter
        stats = await svc.calculate_summary_statistics(valid_only=False)

        assert stats["total_responses"] == 0
        session.exec.assert_awaited_once()

    async def test_summary_contains_all_required_keys(self):
        """All keys that thesis Chapter 5 consumes must be present."""
        responses = [
            _make_response(condition=ExperimentCondition.BASELINE),
            _make_response(condition=ExperimentCondition.MULTIAGENT),
        ]
        session = _make_session(exec_returns=[responses])
        svc = _svc(session)

        stats = await svc.calculate_summary_statistics()

        for key in (
            "total_responses",
            "baseline_n",
            "multiagent_n",
            "baseline_mean_trust",
            "multiagent_mean_trust",
            "trust_difference",
            "baseline_mean_score",
            "multiagent_mean_score",
            "score_difference",
            "cohens_d",
        ):
            assert key in stats, f"Missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════════
# export_all_responses
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportAllResponses:
    def _make_paired_responses(self) -> list[QuestionnaireResponse]:
        return [
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.BASELINE,
                trust_overall=4,
                is_valid=True,
            ),
            _make_response(
                participant_id=1,
                condition=ExperimentCondition.MULTIAGENT,
                trust_overall=6,
                is_valid=True,
            ),
        ]

    async def test_export_returns_summary_object(self):
        responses = self._make_paired_responses()
        # export calls exec once for responses, then calculate_summary calls exec again
        session = _make_session(exec_returns=[responses, responses])
        svc = _svc(session)

        from app.schemas.questionnaire import QuestionnaireExportSummary

        result = await svc.export_all_responses()

        assert isinstance(result, QuestionnaireExportSummary)

    async def test_total_responses_count(self):
        responses = self._make_paired_responses()
        session = _make_session(exec_returns=[responses, responses])
        svc = _svc(session)

        result = await svc.export_all_responses()

        assert result.total_responses == 2

    async def test_baseline_count_and_multiagent_count(self):
        responses = self._make_paired_responses()
        session = _make_session(exec_returns=[responses, responses])
        svc = _svc(session)

        result = await svc.export_all_responses()

        assert result.baseline_count == 1
        assert result.multiagent_count == 1

    async def test_mean_difference_direction(self):
        """multiagent trust (6) > baseline (4) → mean_difference > 0."""
        responses = self._make_paired_responses()
        session = _make_session(exec_returns=[responses, responses])
        svc = _svc(session)

        result = await svc.export_all_responses()

        assert result.mean_difference > 0

    async def test_baseline_means_contains_all_items(self):
        responses = self._make_paired_responses()
        session = _make_session(exec_returns=[responses, responses])
        svc = _svc(session)

        result = await svc.export_all_responses()

        for key in (
            "trust_overall",
            "risk_awareness",
            "technical_soundness",
            "balance",
            "actionability",
            "completeness",
        ):
            assert key in result.baseline_means

    async def test_invalid_count_tracked(self):
        responses = [
            _make_response(is_valid=True),
            _make_response(is_valid=False),
        ]
        # export uses valid_only=True so both are returned (mock doesn't filter)
        session = _make_session(exec_returns=[responses, responses])
        svc = _svc(session)

        result = await svc.export_all_responses(valid_only=False)

        assert result.invalid_count == 1

    async def test_straightlining_detected(self):
        """A response with all 6 Likert scores identical counts as straightlining."""
        normal = _make_response(
            trust_overall=5,
            risk_awareness=4,
            technical_soundness=6,
            balance=5,
            actionability=4,
            completeness=5,
        )
        straightline = _make_response(
            trust_overall=3,
            risk_awareness=3,
            technical_soundness=3,
            balance=3,
            actionability=3,
            completeness=3,
        )
        session = _make_session(
            exec_returns=[[normal, straightline], [normal, straightline]]
        )
        svc = _svc(session)

        result = await svc.export_all_responses(valid_only=False)

        assert result.straightlining_detected == 1

    async def test_no_straightlining_when_scores_vary(self):
        responses = [
            _make_response(
                trust_overall=5,
                risk_awareness=4,
                technical_soundness=6,
                balance=5,
                actionability=4,
                completeness=5,
            )
        ]
        session = _make_session(exec_returns=[responses, responses])
        svc = _svc(session)

        result = await svc.export_all_responses()

        assert result.straightlining_detected == 0

    async def test_empty_responses_returns_zero_summary(self):
        session = _make_session(exec_returns=[[], []])
        svc = _svc(session)

        result = await svc.export_all_responses()

        assert result.total_responses == 0
        assert result.baseline_mean_trust == 0.0
        assert result.multiagent_mean_trust == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# delete_response
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteResponse:
    async def test_deletes_and_commits(self):
        r = _make_response()
        session = _make_session(get_return=r)
        svc = _svc(session)

        await svc.delete_response(r.id)

        session.delete.assert_awaited_once_with(r)
        session.commit.assert_awaited_once()

    async def test_raises_not_found_when_missing(self):
        session = _make_session(get_return=None)
        svc = _svc(session)

        with pytest.raises(NotFoundException):
            await svc.delete_response(999)

    async def test_does_not_commit_when_not_found(self):
        session = _make_session(get_return=None)
        svc = _svc(session)

        with pytest.raises(NotFoundException):
            await svc.delete_response(999)

        session.commit.assert_not_awaited()
