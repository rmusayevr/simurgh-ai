"""
Unit tests for app/services/persona_coding_service.py

Covers every method in PersonaCodingService:
    submit_coding           — happy path, duplicate rejection
    get_coding_by_id        — found / not found
    get_debate_codings      — unfiltered, coder filter, persona filter
    update_coding           — happy path, wrong owner (ForbiddenException)
    delete_coding           — happy path, wrong owner (ForbiddenException)
    generate_debate_summary — full summary, empty codings, low coverage warning,
                              no turns (BadRequest), debate not found,
                              per-persona breakdown math
    write_consistency_to_debate — writes scores back, debate not found
    export_debate_codings   — export shape, empty list
    _get_existing_coding    — hit / miss
    _calculate_persona_breakdown — empty input, full math, QA attribute ranking

DB is mocked — no real PostgreSQL required.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID

from app.models.persona_coding import (
    PersonaCoding,
    InCharacterRating,
    HallucinationRating,
)
from app.models.debate import DebateSession, ConsensusType
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from app.schemas.persona_coding import PersonaCodingCreate, PersonaCodingUpdate
from tests.fixtures.debates import build_debate_session


# ── Factories ─────────────────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc).replace(tzinfo=None)
DEBATE_ID = uuid4()
CODING_ID = uuid4()
CODER_ID = 42


def _make_coding(
    id: UUID | None = None,
    debate_id: UUID | None = None,
    turn_index: int = 0,
    persona: str = "LEGACY_KEEPER",
    in_character: InCharacterRating = InCharacterRating.YES,
    hallucination: HallucinationRating = HallucinationRating.NONE,
    bias_alignment: bool = True,
    quality_attributes: list[str] | None = None,
    coder_id: int = CODER_ID,
    coding_duration_seconds: int | None = 30,
    notes: str | None = None,
    evidence_quote: str | None = None,
) -> PersonaCoding:
    return PersonaCoding(
        id=id or uuid4(),
        debate_id=debate_id or DEBATE_ID,
        turn_index=turn_index,
        persona=persona,
        in_character=in_character,
        hallucination=hallucination,
        bias_alignment=bias_alignment,
        quality_attributes=quality_attributes or ["reliability", "scalability"],
        coder_id=coder_id,
        coding_duration_seconds=coding_duration_seconds,
        notes=notes,
        evidence_quote=evidence_quote,
        created_at=NOW,
        updated_at=NOW,
    )


def _make_create_data(
    debate_id: UUID | None = None,
    turn_index: int = 0,
    persona: str = "legacy_keeper",
    in_character: InCharacterRating = InCharacterRating.YES,
    coder_id: int = CODER_ID,
) -> PersonaCodingCreate:
    return PersonaCodingCreate(
        debate_id=debate_id or DEBATE_ID,
        turn_index=turn_index,
        persona=persona,
        in_character=in_character,
        coder_id=coder_id,
    )


def _make_debate(
    id: UUID | None = None,
    total_turns: int = 6,
    consensus_reached: bool = True,
) -> DebateSession:
    return build_debate_session(
        id=id or DEBATE_ID,
        total_turns=total_turns,
        consensus_reached=consensus_reached,
        consensus_type=ConsensusType.COMPROMISE if consensus_reached else None,
    )


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


def _service(session: AsyncMock):
    from app.services.persona_coding_service import PersonaCodingService

    return PersonaCodingService(session=session)


# ═══════════════════════════════════════════════════════════════════════════════
# submit_coding
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubmitCoding:
    async def test_creates_coding_record(self):
        """Happy path — no duplicate, record is created and returned."""
        session = _make_session(exec_returns=[None])  # _get_existing_coding → None
        coding = _make_coding()
        session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", coding.id) or obj
        )

        svc = _service(session)
        data = _make_create_data()
        await svc.submit_coding(data)

        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    async def test_raises_bad_request_on_duplicate(self):
        """Same coder coding the same turn twice raises BadRequestException."""
        existing = _make_coding()
        session = _make_session(exec_returns=[existing])

        svc = _service(session)
        with pytest.raises(BadRequestException, match="already coded"):
            await svc.submit_coding(_make_create_data())

    async def test_new_coding_has_correct_fields(self):
        """Fields from PersonaCodingCreate are transferred to the model."""
        session = _make_session(exec_returns=[None])
        svc = _service(session)

        data = _make_create_data(
            turn_index=3,
            persona="INNOVATOR",
            in_character=InCharacterRating.PARTIAL,
        )

        # Capture what was passed to session.add
        added_object = None

        def _capture(obj):
            nonlocal added_object
            added_object = obj

        session.add = MagicMock(side_effect=_capture)

        await svc.submit_coding(data)

        assert added_object is not None
        assert added_object.turn_index == 3
        assert added_object.persona == "innovator"
        assert added_object.in_character == InCharacterRating.PARTIAL

    async def test_does_not_commit_if_duplicate(self):
        """Commit should never be called when a duplicate is detected."""
        existing = _make_coding()
        session = _make_session(exec_returns=[existing])
        svc = _service(session)

        with pytest.raises(BadRequestException):
            await svc.submit_coding(_make_create_data())

        session.commit.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════════
# get_coding_by_id
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetCodingById:
    async def test_returns_coding_when_found(self):
        coding = _make_coding(id=CODING_ID)
        session = _make_session(get_return=coding)
        svc = _service(session)

        result = await svc.get_coding_by_id(CODING_ID)
        assert result.id == CODING_ID

    async def test_raises_not_found_when_missing(self):
        session = _make_session(get_return=None)
        svc = _service(session)

        with pytest.raises(NotFoundException, match=str(CODING_ID)):
            await svc.get_coding_by_id(CODING_ID)

    async def test_calls_session_get_with_correct_args(self):
        session = _make_session(get_return=_make_coding(id=CODING_ID))
        svc = _service(session)

        await svc.get_coding_by_id(CODING_ID)
        session.get.assert_awaited_once_with(PersonaCoding, CODING_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# get_debate_codings
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetDebateCodings:
    async def test_returns_all_codings_for_debate(self):
        codings = [_make_coding(turn_index=i) for i in range(3)]
        session = _make_session(exec_returns=[codings])
        svc = _service(session)

        result = await svc.get_debate_codings(DEBATE_ID)
        assert len(result) == 3

    async def test_returns_empty_list_when_no_codings(self):
        session = _make_session(exec_returns=[[]])
        svc = _service(session)

        result = await svc.get_debate_codings(DEBATE_ID)
        assert result == []

    async def test_coder_filter_applied(self):
        """Coder ID filter doesn't crash and returns list."""
        codings = [_make_coding(coder_id=99)]
        session = _make_session(exec_returns=[codings])
        svc = _service(session)

        result = await svc.get_debate_codings(DEBATE_ID, coder_id=99)
        assert len(result) == 1

    async def test_persona_filter_applied(self):
        """Persona filter doesn't crash and returns list."""
        codings = [_make_coding(persona="INNOVATOR")]
        session = _make_session(exec_returns=[codings])
        svc = _service(session)

        result = await svc.get_debate_codings(DEBATE_ID, persona="INNOVATOR")
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# update_coding
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateCoding:
    async def test_updates_field_values(self):
        coding = _make_coding(
            id=CODING_ID, coder_id=CODER_ID, in_character=InCharacterRating.YES
        )
        session = _make_session(get_return=coding)
        svc = _service(session)

        update = PersonaCodingUpdate(in_character=InCharacterRating.PARTIAL)
        result = await svc.update_coding(CODING_ID, update, requester_id=CODER_ID)

        assert result.in_character == InCharacterRating.PARTIAL
        session.commit.assert_awaited_once()

    async def test_raises_forbidden_when_wrong_owner(self):
        coding = _make_coding(id=CODING_ID, coder_id=CODER_ID)
        session = _make_session(get_return=coding)
        svc = _service(session)

        update = PersonaCodingUpdate(notes="Changed note")
        with pytest.raises(ForbiddenException, match="own coding"):
            await svc.update_coding(CODING_ID, update, requester_id=9999)

    async def test_raises_not_found_when_coding_missing(self):
        session = _make_session(get_return=None)
        svc = _service(session)

        update = PersonaCodingUpdate(notes="test")
        with pytest.raises(NotFoundException):
            await svc.update_coding(CODING_ID, update, requester_id=CODER_ID)

    async def test_only_provided_fields_are_updated(self):
        coding = _make_coding(
            id=CODING_ID,
            coder_id=CODER_ID,
            in_character=InCharacterRating.YES,
            hallucination=HallucinationRating.NONE,
        )
        session = _make_session(get_return=coding)
        svc = _service(session)

        # Only update notes — in_character should be unchanged
        update = PersonaCodingUpdate(notes="New note")
        result = await svc.update_coding(CODING_ID, update, requester_id=CODER_ID)

        assert result.in_character == InCharacterRating.YES
        assert result.notes == "New note"

    async def test_sets_updated_at_timestamp(self):
        coding = _make_coding(id=CODING_ID, coder_id=CODER_ID)
        session = _make_session(get_return=coding)
        svc = _service(session)

        update = PersonaCodingUpdate(notes="timestamped update")
        result = await svc.update_coding(CODING_ID, update, requester_id=CODER_ID)

        assert result.updated_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# delete_coding
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteCoding:
    async def test_deletes_when_owner(self):
        coding = _make_coding(id=CODING_ID, coder_id=CODER_ID)
        session = _make_session(get_return=coding)
        svc = _service(session)

        await svc.delete_coding(CODING_ID, requester_id=CODER_ID)

        session.delete.assert_awaited_once_with(coding)
        session.commit.assert_awaited_once()

    async def test_raises_forbidden_when_not_owner(self):
        coding = _make_coding(id=CODING_ID, coder_id=CODER_ID)
        session = _make_session(get_return=coding)
        svc = _service(session)

        with pytest.raises(ForbiddenException, match="own coding"):
            await svc.delete_coding(CODING_ID, requester_id=9999)

    async def test_raises_not_found_when_missing(self):
        session = _make_session(get_return=None)
        svc = _service(session)

        with pytest.raises(NotFoundException):
            await svc.delete_coding(CODING_ID, requester_id=CODER_ID)

    async def test_does_not_delete_if_wrong_owner(self):
        coding = _make_coding(id=CODING_ID, coder_id=CODER_ID)
        session = _make_session(get_return=coding)
        svc = _service(session)

        with pytest.raises(ForbiddenException):
            await svc.delete_coding(CODING_ID, requester_id=1)

        session.delete.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════════
# generate_debate_summary
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateDebateSummary:
    def _three_persona_codings(self) -> list[PersonaCoding]:
        """One coding per persona — fully consistent, no hallucination."""
        return [
            _make_coding(
                persona="LEGACY_KEEPER",
                turn_index=0,
                in_character=InCharacterRating.YES,
            ),
            _make_coding(
                persona="INNOVATOR", turn_index=1, in_character=InCharacterRating.YES
            ),
            _make_coding(
                persona="MEDIATOR", turn_index=2, in_character=InCharacterRating.YES
            ),
        ]

    async def test_raises_not_found_when_debate_missing(self):
        session = _make_session(get_return=None)
        svc = _service(session)

        with pytest.raises(NotFoundException):
            await svc.generate_debate_summary(DEBATE_ID)

    async def test_raises_bad_request_when_debate_has_no_turns(self):
        debate = _make_debate(total_turns=0)
        session = _make_session(get_return=debate)
        svc = _service(session)

        with pytest.raises(BadRequestException, match="no turns"):
            await svc.generate_debate_summary(DEBATE_ID)

    async def test_raises_bad_request_when_no_codings(self):
        debate = _make_debate(total_turns=6)
        session = _make_session(get_return=debate, exec_returns=[[]])
        svc = _service(session)

        with pytest.raises(BadRequestException, match="No coding records"):
            await svc.generate_debate_summary(DEBATE_ID)

    async def test_returns_summary_with_correct_debate_id(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=3)
        codings = self._three_persona_codings()
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.debate_id == DEBATE_ID

    async def test_summary_turns_coded_count(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=6)
        codings = self._three_persona_codings()
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.turns_coded == 3
        assert summary.total_turns_in_debate == 6

    async def test_coding_coverage_calculated(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=10)
        codings = self._three_persona_codings()  # 3 out of 10
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert abs(summary.coding_coverage - 0.3) < 0.01

    async def test_overall_consistency_rate_all_yes(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=3)
        codings = self._three_persona_codings()  # all YES
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.overall_consistency_rate == 1.0

    async def test_overall_consistency_rate_mixed(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=3)
        codings = [
            _make_coding(persona="LEGACY_KEEPER", in_character=InCharacterRating.YES),
            _make_coding(persona="INNOVATOR", in_character=InCharacterRating.PARTIAL),
            _make_coding(persona="MEDIATOR", in_character=InCharacterRating.NO),
        ]
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        # YES=1, PARTIAL=1, NO=1 → (1+1)/3 = 0.667
        assert abs(summary.overall_consistency_rate - 0.667) < 0.01

    async def test_hallucination_rate_calculated(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=2)
        codings = [
            _make_coding(hallucination=HallucinationRating.MINOR),
            _make_coding(hallucination=HallucinationRating.NONE),
        ]
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.overall_hallucination_rate == 0.5

    async def test_coder_ids_deduped(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=3)
        codings = [
            _make_coding(coder_id=1),
            _make_coding(coder_id=1),
            _make_coding(coder_id=2),
        ]
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert set(summary.coder_ids) == {1, 2}

    async def test_total_coding_time_summed(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=2)
        codings = [
            _make_coding(coding_duration_seconds=30),
            _make_coding(coding_duration_seconds=45),
        ]
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.total_coding_time_seconds == 75

    async def test_per_persona_breakdown_populated(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=3)
        codings = self._three_persona_codings()
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.legacy_keeper.total_turns_coded == 1
        assert summary.innovator.total_turns_coded == 1
        assert summary.mediator.total_turns_coded == 1

    async def test_low_coverage_does_not_raise(self):
        """< 20% coverage logs a warning but does NOT raise an exception."""
        debate = _make_debate(id=DEBATE_ID, total_turns=100)
        codings = [_make_coding(turn_index=0)]  # 1/100 = 1% coverage
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        # Should not raise — just logs a warning
        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.coding_coverage < 0.20
        assert not summary.meets_sampling_threshold

    async def test_meets_sampling_threshold_at_20_percent(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=10)
        codings = [_make_coding(turn_index=i) for i in range(2)]  # 2/10 = 20%
        session = _make_session(get_return=debate, exec_returns=[codings])
        svc = _service(session)

        summary = await svc.generate_debate_summary(DEBATE_ID)
        assert summary.meets_sampling_threshold is True


# ═══════════════════════════════════════════════════════════════════════════════
# write_consistency_to_debate
# ═══════════════════════════════════════════════════════════════════════════════


class TestWriteConsistencyToDebate:
    async def test_writes_scores_to_debate_session(self):
        debate = _make_debate(id=DEBATE_ID, total_turns=3)

        # session.get is called twice: once in generate_debate_summary, once after
        # session.exec is called once: get_debate_codings inside generate_summary
        codings = [
            _make_coding(persona="LEGACY_KEEPER", in_character=InCharacterRating.YES),
            _make_coding(persona="INNOVATOR", in_character=InCharacterRating.YES),
            _make_coding(persona="MEDIATOR", in_character=InCharacterRating.PARTIAL),
        ]

        session = AsyncMock()
        session.get = AsyncMock(side_effect=[debate, debate])
        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=codings)
        result_mock.first = MagicMock(return_value=None)
        session.exec = AsyncMock(return_value=result_mock)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        svc = _service(session)
        result = await svc.write_consistency_to_debate(DEBATE_ID)

        # legacy_keeper and innovator both YES → score 1.0
        # mediator PARTIAL → score 0.5
        assert result.legacy_keeper_consistency == 1.0
        assert result.innovator_consistency == 1.0
        assert result.mediator_consistency == 0.5
        session.commit.assert_awaited()

    async def test_raises_not_found_when_debate_missing_after_summary(self):
        """Debate disappears between generate_summary and the second session.get."""
        debate = _make_debate(id=DEBATE_ID, total_turns=3)
        codings = [
            _make_coding(persona="LEGACY_KEEPER"),
            _make_coding(persona="INNOVATOR"),
            _make_coding(persona="MEDIATOR"),
        ]

        session = AsyncMock()
        # First get → found (for generate_summary), second get → None
        session.get = AsyncMock(side_effect=[debate, None])
        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=codings)
        result_mock.first = MagicMock(return_value=None)
        session.exec = AsyncMock(return_value=result_mock)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        svc = _service(session)
        with pytest.raises(NotFoundException):
            await svc.write_consistency_to_debate(DEBATE_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# export_debate_codings
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportDebateCodings:
    async def test_returns_empty_list_when_no_codings(self):
        session = _make_session(exec_returns=[[]])
        svc = _service(session)

        rows = await svc.export_debate_codings(DEBATE_ID)
        assert rows == []

    async def test_export_row_shape(self):
        coding = _make_coding(turn_index=2, persona="INNOVATOR")
        session = _make_session(exec_returns=[[coding]])
        svc = _service(session)

        rows = await svc.export_debate_codings(DEBATE_ID)
        assert len(rows) == 1
        row = rows[0]

        for key in (
            "debate_id",
            "turn_index",
            "persona",
            "in_character",
            "consistency_score",
            "hallucination",
            "hallucination_score",
            "bias_alignment",
            "quality_attribute_count",
            "coder_id",
            "coding_duration_seconds",
            "created_at",
        ):
            assert key in row, f"Missing key: {key}"

    async def test_export_consistency_score_values(self):
        codings = [
            _make_coding(in_character=InCharacterRating.YES),
            _make_coding(in_character=InCharacterRating.PARTIAL),
            _make_coding(in_character=InCharacterRating.NO),
        ]
        session = _make_session(exec_returns=[codings])
        svc = _service(session)

        rows = await svc.export_debate_codings(DEBATE_ID)
        scores = {row["in_character"]: row["consistency_score"] for row in rows}
        assert scores["yes"] == 1.0
        assert scores["partial"] == 0.5
        assert scores["no"] == 0.0

    async def test_export_hallucination_score_values(self):
        codings = [
            _make_coding(hallucination=HallucinationRating.NONE),
            _make_coding(hallucination=HallucinationRating.MINOR),
            _make_coding(hallucination=HallucinationRating.MAJOR),
        ]
        session = _make_session(exec_returns=[codings])
        svc = _service(session)

        rows = await svc.export_debate_codings(DEBATE_ID)
        scores = {row["hallucination"]: row["hallucination_score"] for row in rows}
        assert scores["no"] == 0.0
        assert scores["minor"] == 0.5
        assert scores["major"] == 1.0

    async def test_debate_id_is_string_in_export(self):
        coding = _make_coding()
        session = _make_session(exec_returns=[[coding]])
        svc = _service(session)

        rows = await svc.export_debate_codings(DEBATE_ID)
        assert isinstance(rows[0]["debate_id"], str)


# ═══════════════════════════════════════════════════════════════════════════════
# _get_existing_coding (private helper)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetExistingCoding:
    async def test_returns_none_when_no_match(self):
        session = _make_session(exec_returns=[None])
        svc = _service(session)

        result = await svc._get_existing_coding(
            debate_id=DEBATE_ID, turn_index=0, coder_id=CODER_ID
        )
        assert result is None

    async def test_returns_coding_when_found(self):
        coding = _make_coding()
        session = _make_session(exec_returns=[coding])
        svc = _service(session)

        result = await svc._get_existing_coding(
            debate_id=DEBATE_ID, turn_index=0, coder_id=CODER_ID
        )
        assert result is coding


# ═══════════════════════════════════════════════════════════════════════════════
# _calculate_persona_breakdown (private helper — pure logic, no DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculatePersonaBreakdown:
    def _svc(self):
        return _service(_make_session())

    def test_empty_codings_returns_zero_breakdown(self):
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("legacy_keeper", [])

        assert breakdown.total_turns_coded == 0
        assert breakdown.fully_consistent == 0
        assert breakdown.mean_consistency_score == 0.0
        assert breakdown.consistency_rate == 0.0

    def test_all_yes_gives_score_1(self):
        codings = [_make_coding(in_character=InCharacterRating.YES) for _ in range(4)]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("innovator", codings)

        assert breakdown.fully_consistent == 4
        assert breakdown.mean_consistency_score == 1.0

    def test_all_no_gives_score_0(self):
        codings = [_make_coding(in_character=InCharacterRating.NO) for _ in range(3)]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("mediator", codings)

        assert breakdown.inconsistent == 3
        assert breakdown.mean_consistency_score == 0.0

    def test_mixed_ratings_mean_score(self):
        codings = [
            _make_coding(in_character=InCharacterRating.YES),  # 1.0
            _make_coding(in_character=InCharacterRating.PARTIAL),  # 0.5
            _make_coding(in_character=InCharacterRating.NO),  # 0.0
        ]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("legacy_keeper", codings)

        # mean = (1.0 + 0.5 + 0.0) / 3 ≈ 0.5
        assert abs(breakdown.mean_consistency_score - 0.5) < 0.01

    def test_hallucination_count_minor_and_major(self):
        codings = [
            _make_coding(hallucination=HallucinationRating.NONE),
            _make_coding(hallucination=HallucinationRating.MINOR),
            _make_coding(hallucination=HallucinationRating.MAJOR),
        ]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("innovator", codings)

        assert breakdown.hallucination_count == 2
        assert breakdown.major_hallucination_count == 1

    def test_bias_aligned_count(self):
        codings = [
            _make_coding(bias_alignment=True),
            _make_coding(bias_alignment=True),
            _make_coding(bias_alignment=False),
        ]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("mediator", codings)

        assert breakdown.bias_aligned_count == 2

    def test_top_quality_attributes_sorted_by_frequency(self):
        codings = [
            _make_coding(
                quality_attributes=["reliability", "scalability", "reliability"]
            ),
            _make_coding(quality_attributes=["reliability", "performance"]),
            _make_coding(quality_attributes=["scalability", "performance"]),
        ]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("legacy_keeper", codings)

        # reliability appears most (3x), should be first
        assert breakdown.top_quality_attributes[0] == "reliability"

    def test_top_qa_capped_at_five(self):
        attrs = [f"attr_{i}" for i in range(10)]
        codings = [_make_coding(quality_attributes=attrs)]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("innovator", codings)

        assert len(breakdown.top_quality_attributes) <= 5

    def test_consistency_rate_property(self):
        codings = [
            _make_coding(in_character=InCharacterRating.YES),
            _make_coding(in_character=InCharacterRating.PARTIAL),
            _make_coding(in_character=InCharacterRating.NO),
            _make_coding(in_character=InCharacterRating.NO),
        ]
        svc = self._svc()
        breakdown = svc._calculate_persona_breakdown("mediator", codings)

        # (YES + PARTIAL) / total = 2/4 = 0.5
        assert breakdown.consistency_rate == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# PersonaCodingCreate schema validators (no DB — pure Pydantic)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPersonaCodingCreateValidation:
    def test_invalid_persona_raises_value_error(self):
        with pytest.raises(Exception, match="persona"):
            PersonaCodingCreate(
                debate_id=uuid4(),
                turn_index=0,
                persona="unknown_persona",
                in_character=InCharacterRating.YES,
                coder_id=1,
            )

    def test_valid_personas_accepted(self):
        for persona in ("legacy_keeper", "innovator", "mediator"):
            create = PersonaCodingCreate(
                debate_id=uuid4(),
                turn_index=0,
                persona=persona,
                in_character=InCharacterRating.YES,
                coder_id=1,
            )
            assert create.persona == persona

    def test_major_hallucination_requires_notes_or_evidence(self):
        with pytest.raises(Exception, match="Major hallucination"):
            PersonaCodingCreate(
                debate_id=uuid4(),
                turn_index=0,
                persona="INNOVATOR",
                in_character=InCharacterRating.YES,
                hallucination=HallucinationRating.MAJOR,
                coder_id=1,
                # No notes, no evidence_quote
            )

    def test_major_hallucination_with_notes_is_valid(self):
        create = PersonaCodingCreate(
            debate_id=uuid4(),
            turn_index=0,
            persona="INNOVATOR",
            in_character=InCharacterRating.YES,
            hallucination=HallucinationRating.MAJOR,
            notes="The persona fabricated a statistic.",
            coder_id=1,
        )
        assert create.hallucination == HallucinationRating.MAJOR

    def test_major_hallucination_with_evidence_quote_is_valid(self):
        create = PersonaCodingCreate(
            debate_id=uuid4(),
            turn_index=0,
            persona="MEDIATOR",
            in_character=InCharacterRating.PARTIAL,
            hallucination=HallucinationRating.MAJOR,
            evidence_quote="'Studies show 99% success' — fabricated.",
            coder_id=1,
        )
        assert create.evidence_quote is not None

    def test_minor_hallucination_needs_no_note(self):
        create = PersonaCodingCreate(
            debate_id=uuid4(),
            turn_index=1,
            persona="LEGACY_KEEPER",
            in_character=InCharacterRating.YES,
            hallucination=HallucinationRating.MINOR,
            coder_id=1,
        )
        assert create.hallucination == HallucinationRating.MINOR
