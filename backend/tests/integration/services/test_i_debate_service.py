"""
Phase 6 - Integration: DebateService DB persistence against real PostgreSQL.

Note: Full debate conduct requires Anthropic API calls (mocked in unit tests).
These integration tests verify DB-layer behaviour: session creation,
history persistence, and read operations without invoking the AI.
"""

from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole
from app.models.proposal import Proposal, ProposalStatus, AgentPersona
from app.models.debate import DebateSession
from app.core.security import hash_password
from app.core.exceptions import NotFoundException
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService
from app.services.debate_service import DebateService


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("Password123!"),
        full_name="Test",
        role=UserRole.USER,
        is_active=True,
        is_superuser=False,
        email_verified=True,
        terms_accepted=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_project_and_proposal(db: AsyncSession, owner_id: int):
    project = await ProjectService(db).create_project(
        project_data=ProjectCreate(name="Debate Project", description="desc"),
        owner_id=owner_id,
    )
    proposal = Proposal(
        project_id=project.id,
        task_description="Should we adopt event sourcing?",
        created_by_id=owner_id,
        status=ProposalStatus.COMPLETED,
    )
    db.add(proposal)
    await db.flush()
    return project, proposal


async def _make_debate_session(db: AsyncSession, proposal_id: int) -> DebateSession:
    from datetime import datetime, timezone

    debate = DebateSession(
        proposal_id=proposal_id,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        consensus_reached=False,
        total_turns=0,
    )
    db.add(debate)
    await db.flush()
    return debate


class TestDebateSessionPersistence:
    async def test_debate_session_row_is_created(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "deb_create@example.com")
        _, proposal = await _make_project_and_proposal(db_session, owner.id)

        debate = await _make_debate_session(db_session, proposal.id)

        assert debate.id is not None
        fetched = await db_session.get(DebateSession, debate.id)
        assert fetched is not None
        assert fetched.proposal_id == proposal.id

    async def test_debate_session_starts_with_empty_history(
        self, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "deb_empty@example.com")
        _, proposal = await _make_project_and_proposal(db_session, owner.id)

        debate = await _make_debate_session(db_session, proposal.id)
        assert debate.debate_history is None or debate.debate_history == []

    async def test_debate_add_turn_persists_to_jsonb(self, db_session: AsyncSession):
        """add_turn() must persist the turn dict to the debate_history JSONB column."""
        from sqlalchemy.orm.attributes import flag_modified

        owner = await _make_user(db_session, "deb_turn@example.com")
        _, proposal = await _make_project_and_proposal(db_session, owner.id)
        debate = await _make_debate_session(db_session, proposal.id)

        debate.add_turn(
            persona=AgentPersona.LEGACY_KEEPER.value,
            response="We must preserve backward compatibility.",
            sentiment="agreeable",
            key_points=["compatibility", "stability"],
            bias_alignment_score=0.8,
        )
        flag_modified(debate, "debate_history")
        db_session.add(debate)
        await db_session.flush()

        fetched = await db_session.get(DebateSession, debate.id)
        assert fetched.debate_history is not None
        assert len(fetched.debate_history) == 1
        assert fetched.debate_history[0]["persona"] == AgentPersona.LEGACY_KEEPER.value

    async def test_multiple_turns_accumulate_in_history(self, db_session: AsyncSession):
        """Three consecutive add_turn() calls must produce three history entries."""
        from sqlalchemy.orm.attributes import flag_modified

        owner = await _make_user(db_session, "deb_multi@example.com")
        _, proposal = await _make_project_and_proposal(db_session, owner.id)
        debate = await _make_debate_session(db_session, proposal.id)

        for persona in [
            AgentPersona.LEGACY_KEEPER,
            AgentPersona.INNOVATOR,
            AgentPersona.MEDIATOR,
        ]:
            debate.add_turn(
                persona=persona.value,
                response=f"Response from {persona.value}",
                sentiment="agreeable",
                key_points=[],
                bias_alignment_score=0.5,
            )
        flag_modified(debate, "debate_history")
        db_session.add(debate)
        await db_session.flush()

        fetched = await db_session.get(DebateSession, debate.id)
        assert len(fetched.debate_history) == 3


class TestDebateServiceRead:
    async def test_get_debate_by_id_returns_session(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "deb_read@example.com")
        _, proposal = await _make_project_and_proposal(db_session, owner.id)
        debate = await _make_debate_session(db_session, proposal.id)

        svc = DebateService(db_session)
        fetched = await svc.get_debate_by_id(debate.id, owner.id, UserRole.USER)

        assert fetched.id == debate.id

    async def test_get_nonexistent_debate_raises_not_found(
        self, db_session: AsyncSession
    ):
        import uuid

        owner = await _make_user(db_session, "deb_404@example.com")
        svc = DebateService(db_session)

        with pytest.raises(NotFoundException):
            await svc.get_debate_by_id(uuid.uuid4(), owner.id, UserRole.USER)

    async def test_get_debates_by_proposal_returns_list(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "deb_list@example.com")
        _, proposal = await _make_project_and_proposal(db_session, owner.id)
        await _make_debate_session(db_session, proposal.id)
        await _make_debate_session(db_session, proposal.id)

        svc = DebateService(db_session)
        debates = await svc.get_debates_by_proposal(
            proposal.id, owner.id, UserRole.USER
        )

        assert len(debates) == 2

    async def test_get_debate_turns_returns_sorted_history(
        self, db_session: AsyncSession
    ):
        from sqlalchemy.orm.attributes import flag_modified

        owner = await _make_user(db_session, "deb_turns@example.com")
        _, proposal = await _make_project_and_proposal(db_session, owner.id)
        debate = await _make_debate_session(db_session, proposal.id)

        for persona in [AgentPersona.LEGACY_KEEPER, AgentPersona.INNOVATOR]:
            debate.add_turn(
                persona=persona.value,
                response="Response",
                sentiment="agreeable",
                key_points=[],
                bias_alignment_score=0.5,
            )
        flag_modified(debate, "debate_history")
        db_session.add(debate)
        await db_session.flush()

        svc = DebateService(db_session)
        turns = await svc.get_debate_turns(debate.id, owner.id, UserRole.USER)

        assert len(turns) == 2
        turn_numbers = [t["turn_number"] for t in turns]
        assert turn_numbers == sorted(turn_numbers)
