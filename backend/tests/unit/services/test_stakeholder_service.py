"""
Unit tests for app/services/stakeholder_service.py

Covers:
    - Mendelow Matrix quadrant logic (all four quadrants)
    - power_interest_quadrant property on Stakeholder model
    - risk_level calculation
    - needs_attention logic
    - Sentiment properties (is_positive, is_negative, risk_score)
    - InfluenceLevel / InterestLevel weights
    - get_stakeholder_matrix grouping
    - Strategy cache hit (returns cached plan without AI call)
    - get_by_id raises NotFoundException when session returns None
    - delete_stakeholder calls session.delete

All DB calls are mocked via AsyncMock session.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.stakeholder import InfluenceLevel, InterestLevel, Sentiment
from app.models.user import UserRole
from app.core.exceptions import NotFoundException
from tests.fixtures.stakeholders import (
    build_stakeholder,
    build_key_player,
    build_keep_satisfied,
    build_keep_informed,
    build_monitor,
    build_blocker,
    build_champion,
)
from tests.fixtures.projects import build_project


# ══════════════════════════════════════════════════════════════════
# Mendelow Matrix quadrant logic (pure model property)
# ══════════════════════════════════════════════════════════════════


class TestMendelowMatrixQuadrants:
    def test_high_influence_high_interest_is_manage_closely(self):
        s = build_key_player()
        assert s.power_interest_quadrant == "Manage Closely"

    def test_high_influence_low_interest_is_keep_satisfied(self):
        s = build_keep_satisfied()
        assert s.power_interest_quadrant == "Keep Satisfied"

    def test_low_influence_high_interest_is_keep_informed(self):
        s = build_keep_informed()
        assert s.power_interest_quadrant == "Keep Informed"

    def test_low_influence_low_interest_is_monitor(self):
        s = build_monitor()
        assert s.power_interest_quadrant == "Monitor"

    def test_medium_influence_medium_interest_is_monitor(self):
        """MEDIUM is treated as 'not HIGH' → falls into lower quadrants."""
        s = build_stakeholder(
            influence=InfluenceLevel.MEDIUM,
            interest=InterestLevel.MEDIUM,
        )
        assert s.power_interest_quadrant == "Monitor"

    def test_high_influence_medium_interest_is_keep_satisfied(self):
        s = build_stakeholder(
            influence=InfluenceLevel.HIGH,
            interest=InterestLevel.MEDIUM,
        )
        assert s.power_interest_quadrant == "Keep Satisfied"

    def test_medium_influence_high_interest_is_keep_informed(self):
        s = build_stakeholder(
            influence=InfluenceLevel.MEDIUM,
            interest=InterestLevel.HIGH,
        )
        assert s.power_interest_quadrant == "Keep Informed"


# ══════════════════════════════════════════════════════════════════
# InfluenceLevel and InterestLevel weights
# ══════════════════════════════════════════════════════════════════


class TestLevelWeights:
    def test_high_influence_weight_is_3(self):
        assert InfluenceLevel.HIGH.weight == 3

    def test_medium_influence_weight_is_2(self):
        assert InfluenceLevel.MEDIUM.weight == 2

    def test_low_influence_weight_is_1(self):
        assert InfluenceLevel.LOW.weight == 1

    def test_high_interest_weight_is_3(self):
        assert InterestLevel.HIGH.weight == 3

    def test_medium_interest_weight_is_2(self):
        assert InterestLevel.MEDIUM.weight == 2

    def test_low_interest_weight_is_1(self):
        assert InterestLevel.LOW.weight == 1


# ══════════════════════════════════════════════════════════════════
# Sentiment properties
# ══════════════════════════════════════════════════════════════════


class TestSentimentProperties:
    def test_champion_is_positive(self):
        assert Sentiment.CHAMPION.is_positive is True

    def test_supportive_is_positive(self):
        assert Sentiment.SUPPORTIVE.is_positive is True

    def test_neutral_is_not_positive(self):
        assert Sentiment.NEUTRAL.is_positive is False

    def test_resistant_is_negative(self):
        assert Sentiment.RESISTANT.is_negative is True

    def test_blocker_is_negative(self):
        assert Sentiment.BLOCKER.is_negative is True

    def test_champion_is_not_negative(self):
        assert Sentiment.CHAMPION.is_negative is False

    def test_risk_scores_ordered_ascending(self):
        scores = [
            s.risk_score
            for s in [
                Sentiment.CHAMPION,
                Sentiment.SUPPORTIVE,
                Sentiment.NEUTRAL,
                Sentiment.CONCERNED,
                Sentiment.RESISTANT,
                Sentiment.BLOCKER,
            ]
        ]
        assert scores == sorted(scores)

    def test_champion_lowest_risk_score(self):
        assert Sentiment.CHAMPION.risk_score == 0

    def test_blocker_highest_risk_score(self):
        assert Sentiment.BLOCKER.risk_score == 5


# ══════════════════════════════════════════════════════════════════
# risk_level calculation
# ══════════════════════════════════════════════════════════════════


class TestRiskLevel:
    def test_high_influence_blocker_is_critical(self):
        s = build_blocker()  # HIGH influence + BLOCKER
        assert s.risk_level == "Critical"

    def test_high_influence_resistant_is_high(self):
        s = build_stakeholder(
            influence=InfluenceLevel.HIGH, sentiment=Sentiment.RESISTANT
        )
        # risk_score=4, weight=3 → 12 → "Critical" (>=12)
        assert s.risk_level == "Critical"

    def test_low_influence_blocker_is_medium(self):
        s = build_stakeholder(influence=InfluenceLevel.LOW, sentiment=Sentiment.BLOCKER)
        # risk_score=5, weight=1 → 5 → "Medium" (>=4)
        assert s.risk_level == "Medium"

    def test_champion_is_low_risk(self):
        s = build_champion()
        assert s.risk_level == "Low"

    def test_supportive_is_low_risk(self):
        s = build_stakeholder(sentiment=Sentiment.SUPPORTIVE)
        assert s.risk_level == "Low"


# ══════════════════════════════════════════════════════════════════
# needs_attention logic
# ══════════════════════════════════════════════════════════════════


class TestNeedsAttention:
    def test_high_influence_resistant_needs_attention(self):
        s = build_stakeholder(
            influence=InfluenceLevel.HIGH, sentiment=Sentiment.RESISTANT
        )
        assert s.needs_attention is True

    def test_high_influence_blocker_needs_attention(self):
        s = build_blocker()
        assert s.needs_attention is True

    def test_low_influence_blocker_still_needs_attention(self):
        # Blockers always need attention regardless of influence
        s = build_stakeholder(influence=InfluenceLevel.LOW, sentiment=Sentiment.BLOCKER)
        assert s.needs_attention is True

    def test_low_influence_resistant_does_not_need_attention(self):
        s = build_stakeholder(
            influence=InfluenceLevel.LOW, sentiment=Sentiment.RESISTANT
        )
        assert s.needs_attention is False

    def test_high_influence_champion_does_not_need_attention(self):
        s = build_champion()
        assert s.needs_attention is False

    def test_high_influence_neutral_does_not_need_attention(self):
        s = build_key_player()  # NEUTRAL sentiment
        assert s.needs_attention is False


# ══════════════════════════════════════════════════════════════════
# is_blocker / is_champion helpers
# ══════════════════════════════════════════════════════════════════


class TestHelperProperties:
    def test_is_blocker_true(self):
        assert build_blocker().is_blocker is True

    def test_is_blocker_false_for_neutral(self):
        assert build_key_player().is_blocker is False

    def test_is_champion_true(self):
        assert build_champion().is_champion is True

    def test_is_champion_false_for_neutral(self):
        assert build_key_player().is_champion is False


# ══════════════════════════════════════════════════════════════════
# StakeholderService — get_by_id
# ══════════════════════════════════════════════════════════════════


class TestStakeholderServiceGetById:
    def _make_service(self, session):
        from app.services.stakeholder_service import StakeholderService

        return StakeholderService(session=session)

    async def test_raises_not_found_when_session_returns_none(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = self._make_service(session)
        with pytest.raises(NotFoundException):
            await svc.get_by_id(stakeholder_id=99, user_id=1, user_role=UserRole.USER)

    async def test_returns_stakeholder_when_found(self):
        stakeholder = build_key_player(id=1)
        session = AsyncMock()
        session.get = AsyncMock(return_value=stakeholder)

        svc = self._make_service(session)
        # Patch _assert_can_access_project to not call DB
        svc._assert_can_access_project = AsyncMock()

        result = await svc.get_by_id(
            stakeholder_id=1, user_id=1, user_role=UserRole.USER
        )
        assert result == stakeholder

    async def test_access_check_called_with_correct_project_id(self):
        stakeholder = build_key_player(id=1, project_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=stakeholder)

        svc = self._make_service(session)
        svc._assert_can_access_project = AsyncMock()

        await svc.get_by_id(stakeholder_id=1, user_id=7, user_role=UserRole.USER)
        svc._assert_can_access_project.assert_called_once_with(42, 7, UserRole.USER)


# ══════════════════════════════════════════════════════════════════
# StakeholderService — delete
# ══════════════════════════════════════════════════════════════════


class TestStakeholderServiceDelete:
    def _make_service(self, session):
        from app.services.stakeholder_service import StakeholderService

        return StakeholderService(session=session)

    async def test_delete_calls_session_delete(self):
        stakeholder = build_key_player(id=1)
        session = AsyncMock()

        svc = self._make_service(session)
        svc.get_by_id = AsyncMock(return_value=stakeholder)
        svc._assert_can_manage_project = AsyncMock()

        await svc.delete_stakeholder(
            stakeholder_id=1, user_id=1, user_role=UserRole.USER
        )
        session.delete.assert_called_once_with(stakeholder)
        session.commit.assert_called_once()

    async def test_not_found_propagated_from_get_by_id(self):
        session = AsyncMock()
        svc = self._make_service(session)
        svc.get_by_id = AsyncMock(side_effect=NotFoundException("not found"))

        with pytest.raises(NotFoundException):
            await svc.delete_stakeholder(
                stakeholder_id=99, user_id=1, user_role=UserRole.USER
            )


# ══════════════════════════════════════════════════════════════════
# StakeholderService — strategy cache
# ══════════════════════════════════════════════════════════════════


class TestStakeholderServiceStrategyCache:
    def _make_service(self, session):
        from app.services.stakeholder_service import StakeholderService

        return StakeholderService(session=session)

    async def test_returns_cached_strategy_without_ai_call(self):
        """When strategic_plan is already set, no AI call should be made."""
        stakeholder = build_key_player(id=1)
        stakeholder.strategic_plan = "Existing strategy plan"
        session = AsyncMock()

        svc = self._make_service(session)
        svc.get_by_id = AsyncMock(return_value=stakeholder)

        with patch("app.services.stakeholder_service.ai_service") as mock_ai:
            result = await svc.generate_engagement_strategy(
                stakeholder_id=1,
                user_id=1,
                user_role=UserRole.USER,
                force_regenerate=False,
            )
        mock_ai.generate_strategy.assert_not_called()
        assert result == "Existing strategy plan"

    async def test_force_regenerate_bypasses_cache(self):
        """force_regenerate=True calls AI even when strategy is cached."""
        stakeholder = build_key_player(id=1, project_id=1)
        stakeholder.strategic_plan = "Old strategy"
        project = build_project(id=1)
        session = MagicMock()
        session.get = AsyncMock(return_value=project)
        session.commit = AsyncMock()

        svc = self._make_service(session)
        svc.get_by_id = AsyncMock(return_value=stakeholder)

        with patch("app.services.stakeholder_service.ai_service") as mock_ai:
            mock_ai.build_strategy_prompt.return_value = "prompt"
            mock_ai.generate_strategy = AsyncMock(return_value="New strategy")
            result = await svc.generate_engagement_strategy(
                stakeholder_id=1,
                user_id=1,
                user_role=UserRole.USER,
                force_regenerate=True,
            )
        mock_ai.generate_strategy.assert_called_once()
        assert result == "New strategy"


# ══════════════════════════════════════════════════════════════════
# get_stakeholder_matrix grouping
# ══════════════════════════════════════════════════════════════════


class TestGetStakeholderMatrix:
    def _make_service(self, session):
        from app.services.stakeholder_service import StakeholderService

        return StakeholderService(session=session)

    async def test_matrix_has_four_quadrant_keys(self):
        session = AsyncMock()
        svc = self._make_service(session)
        svc.get_project_stakeholders = AsyncMock(return_value=[])

        result = await svc.get_stakeholder_matrix(
            project_id=1, user_id=1, user_role=UserRole.USER
        )
        assert set(result.keys()) == {
            "key_players",
            "keep_satisfied",
            "keep_informed",
            "monitor",
        }

    async def test_key_player_lands_in_key_players(self):
        session = AsyncMock()
        svc = self._make_service(session)
        svc.get_project_stakeholders = AsyncMock(return_value=[build_key_player(id=1)])
        result = await svc.get_stakeholder_matrix(
            project_id=1, user_id=1, user_role=UserRole.USER
        )
        assert len(result["key_players"]) == 1
        assert result["key_players"][0]["id"] == 1

    async def test_keep_satisfied_stakeholder_grouped_correctly(self):
        session = AsyncMock()
        svc = self._make_service(session)
        svc.get_project_stakeholders = AsyncMock(
            return_value=[build_keep_satisfied(id=2)]
        )
        result = await svc.get_stakeholder_matrix(
            project_id=1, user_id=1, user_role=UserRole.USER
        )
        assert len(result["keep_satisfied"]) == 1

    async def test_mixed_stakeholders_grouped_correctly(self):
        session = AsyncMock()
        svc = self._make_service(session)
        svc.get_project_stakeholders = AsyncMock(
            return_value=[
                build_key_player(id=1),
                build_keep_satisfied(id=2),
                build_keep_informed(id=3),
                build_monitor(id=4),
            ]
        )
        result = await svc.get_stakeholder_matrix(
            project_id=1, user_id=1, user_role=UserRole.USER
        )
        assert len(result["key_players"]) == 1
        assert len(result["keep_satisfied"]) == 1
        assert len(result["keep_informed"]) == 1
        assert len(result["monitor"]) == 1

    async def test_matrix_entry_contains_required_fields(self):
        session = AsyncMock()
        svc = self._make_service(session)
        svc.get_project_stakeholders = AsyncMock(return_value=[build_key_player(id=1)])
        result = await svc.get_stakeholder_matrix(
            project_id=1, user_id=1, user_role=UserRole.USER
        )
        entry = result["key_players"][0]
        assert "id" in entry
        assert "name" in entry
        assert "role" in entry
        assert "sentiment" in entry
        assert "needs_attention" in entry
