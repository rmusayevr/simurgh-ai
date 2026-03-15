"""
Stakeholder factory fixtures.

Covers all four Mendelow Matrix quadrants and all Sentiment values
so unit tests can import a ready-made instance without boilerplate.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.models.stakeholder import (
    Stakeholder,
    InfluenceLevel,
    InterestLevel,
    Sentiment,
)


# ── Low-level factory ──────────────────────────────────────────────────────────


def build_stakeholder(
    id: int = 1,
    name: str = "Alice Johnson",
    role: str = "CTO",
    department: str | None = "Engineering",
    email: str | None = "alice@example.com",
    influence: InfluenceLevel = InfluenceLevel.HIGH,
    interest: InterestLevel = InterestLevel.HIGH,
    sentiment: Sentiment = Sentiment.NEUTRAL,
    notes: str | None = None,
    strategic_plan: str | None = None,
    concerns: str | None = None,
    motivations: str | None = None,
    approval_role: str | None = "cto",
    notify_on_approval_needed: bool = True,
    project_id: int = 1,
) -> Stakeholder:
    """
    Build an in-memory Stakeholder with sensible defaults.

    Defaults to HIGH influence + HIGH interest → "Manage Closely" quadrant.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return Stakeholder(
        id=id,
        name=name,
        role=role,
        department=department,
        email=email,
        influence=influence,
        interest=interest,
        sentiment=sentiment,
        notes=notes,
        strategic_plan=strategic_plan,
        concerns=concerns,
        motivations=motivations,
        approval_role=approval_role,
        notify_on_approval_needed=notify_on_approval_needed,
        project_id=project_id,
        created_at=now,
        updated_at=now,
    )


# ── Quadrant-specific builders ─────────────────────────────────────────────────


def build_key_player(id: int = 1, project_id: int = 1) -> Stakeholder:
    """HIGH influence + HIGH interest → Manage Closely."""
    return build_stakeholder(
        id=id,
        name="Key Player",
        role="CTO",
        influence=InfluenceLevel.HIGH,
        interest=InterestLevel.HIGH,
        project_id=project_id,
    )


def build_keep_satisfied(id: int = 2, project_id: int = 1) -> Stakeholder:
    """HIGH influence + LOW interest → Keep Satisfied."""
    return build_stakeholder(
        id=id,
        name="Board Member",
        role="Board Director",
        influence=InfluenceLevel.HIGH,
        interest=InterestLevel.LOW,
        project_id=project_id,
    )


def build_keep_informed(id: int = 3, project_id: int = 1) -> Stakeholder:
    """LOW influence + HIGH interest → Keep Informed."""
    return build_stakeholder(
        id=id,
        name="Power User",
        role="Senior Developer",
        influence=InfluenceLevel.LOW,
        interest=InterestLevel.HIGH,
        project_id=project_id,
    )


def build_monitor(id: int = 4, project_id: int = 1) -> Stakeholder:
    """LOW influence + LOW interest → Monitor."""
    return build_stakeholder(
        id=id,
        name="Peripheral User",
        role="Junior Analyst",
        influence=InfluenceLevel.LOW,
        interest=InterestLevel.LOW,
        project_id=project_id,
    )


def build_blocker(id: int = 5, project_id: int = 1) -> Stakeholder:
    """HIGH influence BLOCKER — the most dangerous risk profile."""
    return build_stakeholder(
        id=id,
        name="Resistant Executive",
        role="CFO",
        influence=InfluenceLevel.HIGH,
        interest=InterestLevel.HIGH,
        sentiment=Sentiment.BLOCKER,
        project_id=project_id,
    )


def build_champion(id: int = 6, project_id: int = 1) -> Stakeholder:
    """CHAMPION — actively advocating for the project."""
    return build_stakeholder(
        id=id,
        name="Project Champion",
        role="VP Engineering",
        influence=InfluenceLevel.HIGH,
        interest=InterestLevel.HIGH,
        sentiment=Sentiment.CHAMPION,
        project_id=project_id,
    )


# ── pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def test_stakeholder() -> Stakeholder:
    """Default stakeholder: HIGH/HIGH, NEUTRAL — Manage Closely quadrant."""
    return build_key_player()


@pytest.fixture
def test_stakeholder_keep_satisfied() -> Stakeholder:
    """HIGH influence, LOW interest — Keep Satisfied quadrant."""
    return build_keep_satisfied()


@pytest.fixture
def test_stakeholder_keep_informed() -> Stakeholder:
    """LOW influence, HIGH interest — Keep Informed quadrant."""
    return build_keep_informed()


@pytest.fixture
def test_stakeholder_monitor() -> Stakeholder:
    """LOW influence, LOW interest — Monitor quadrant."""
    return build_monitor()


@pytest.fixture
def test_blocker() -> Stakeholder:
    """HIGH influence BLOCKER — critical risk."""
    return build_blocker()


@pytest.fixture
def test_champion() -> Stakeholder:
    """CHAMPION stakeholder — project advocate."""
    return build_champion()


@pytest.fixture
def all_quadrant_stakeholders() -> list[Stakeholder]:
    """
    All four Mendelow Matrix quadrants as a list.

    Useful for parameterized tests or matrix-rendering tests.

    Returns:
        [key_player, keep_satisfied, keep_informed, monitor]
    """
    return [
        build_key_player(id=1),
        build_keep_satisfied(id=2),
        build_keep_informed(id=3),
        build_monitor(id=4),
    ]


@pytest.fixture
def make_stakeholder():
    """
    Parameterizable stakeholder factory.

    Usage:
        def test_custom(make_stakeholder):
            s = make_stakeholder(name="Bob", influence=InfluenceLevel.MEDIUM)
    """
    return build_stakeholder
