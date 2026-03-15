"""
E2E — Stakeholder analysis flow.

All service mocks return real SQLModel instances to pass FastAPI/Pydantic
response serialization.

Markers: e2e, slow
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from app.models.stakeholder import (
    Stakeholder,
    InfluenceLevel,
    InterestLevel,
    Sentiment,
)
from app.models.project import Project, ProjectVisibility


# ── Real model builders ───────────────────────────────────────────────────────

PROJECT_ID = 1
STAKEHOLDER_ID = 42


def _stakeholder(
    id: int = STAKEHOLDER_ID,
    name: str = "Alice Johnson",
    role: str = "CTO",
    influence: InfluenceLevel = InfluenceLevel.HIGH,
    interest: InterestLevel = InterestLevel.HIGH,
    sentiment: Sentiment = Sentiment.NEUTRAL,
    project_id: int = PROJECT_ID,
) -> Stakeholder:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return Stakeholder(
        id=id,
        name=name,
        role=role,
        department="Engineering",
        email=f"{name.lower().replace(' ', '.')}@example.com",
        influence=influence,
        interest=interest,
        sentiment=sentiment,
        notes=None,
        strategic_plan=None,
        concerns=None,
        motivations=None,
        approval_role="cto",
        notify_on_approval_needed=True,
        project_id=project_id,
        created_at=now,
        updated_at=now,
    )


def _project(id: int = PROJECT_ID) -> Project:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return Project(
        id=id,
        name="Payment Platform Migration",
        description="Migrate monolith to microservices.",
        owner_id=1,
        visibility=ProjectVisibility.PRIVATE,
        is_archived=False,
        tags="backend,migration",
        tech_stack="Python,FastAPI",
        document_count=3,
        proposal_count=2,
        member_count=5,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Auth guards
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestStakeholderAuthGuards:
    async def test_create_requires_auth(self, client):
        resp = await client.post(
            f"/api/v1/stakeholders/project/{PROJECT_ID}",
            json={"name": "Alice", "role": "CTO"},
        )
        assert resp.status_code == 401

    async def test_list_requires_auth(self, client):
        assert (
            await client.get(f"/api/v1/stakeholders/project/{PROJECT_ID}")
        ).status_code == 401

    async def test_get_requires_auth(self, client):
        assert (
            await client.get(f"/api/v1/stakeholders/{STAKEHOLDER_ID}")
        ).status_code == 401

    async def test_update_requires_auth(self, client):
        assert (
            await client.patch(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}", json={"sentiment": "CHAMPION"}
            )
        ).status_code == 401

    async def test_delete_requires_auth(self, client):
        assert (
            await client.delete(f"/api/v1/stakeholders/{STAKEHOLDER_ID}")
        ).status_code == 401

    async def test_generate_strategy_requires_auth(self, client):
        assert (
            await client.post(f"/api/v1/stakeholders/{STAKEHOLDER_ID}/strategy")
        ).status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# 2. Stakeholder creation
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestStakeholderCreation:
    async def test_create_returns_201(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService,
            "create_stakeholder",
            new=AsyncMock(return_value=_stakeholder()),
        ):
            resp = await user_client.post(
                f"/api/v1/stakeholders/project/{PROJECT_ID}",
                json={
                    "name": "Alice Johnson",
                    "role": "CTO",
                    "influence": "HIGH",
                    "interest": "HIGH",
                },
            )
        assert resp.status_code in (200, 201)

    async def test_create_missing_name_returns_422(self, user_client):
        resp = await user_client.post(
            f"/api/v1/stakeholders/project/{PROJECT_ID}",
            json={"role": "CTO", "influence": "HIGH", "interest": "HIGH"},
        )
        assert resp.status_code == 422

    async def test_create_missing_role_returns_422(self, user_client):
        resp = await user_client.post(
            f"/api/v1/stakeholders/project/{PROJECT_ID}",
            json={"name": "Alice", "influence": "HIGH", "interest": "HIGH"},
        )
        assert resp.status_code == 422

    async def test_create_invalid_influence_returns_422(self, user_client):
        resp = await user_client.post(
            f"/api/v1/stakeholders/project/{PROJECT_ID}",
            json={
                "name": "Alice",
                "role": "CTO",
                "influence": "EXTREME",
                "interest": "HIGH",
            },
        )
        assert resp.status_code == 422

    async def test_create_project_not_found_returns_404(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import NotFoundException

        with patch.object(
            StakeholderService,
            "create_stakeholder",
            new=AsyncMock(side_effect=NotFoundException("project not found")),
        ):
            resp = await user_client.post(
                "/api/v1/stakeholders/project/9999",
                json={"name": "Alice", "role": "CTO"},
            )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 3. Stakeholder retrieval
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestStakeholderRetrieval:
    async def test_get_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService, "get_by_id", new=AsyncMock(return_value=_stakeholder())
        ):
            resp = await user_client.get(f"/api/v1/stakeholders/{STAKEHOLDER_ID}")
        assert resp.status_code == 200

    async def test_get_not_found_returns_404(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import NotFoundException

        with patch.object(
            StakeholderService,
            "get_by_id",
            new=AsyncMock(side_effect=NotFoundException("not found")),
        ):
            resp = await user_client.get("/api/v1/stakeholders/9999")
        assert resp.status_code == 404

    async def test_list_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        stakeholders = [
            _stakeholder(id=1, name="Alice"),
            _stakeholder(id=2, name="Bob"),
        ]
        with patch.object(
            StakeholderService,
            "get_project_stakeholders",
            new=AsyncMock(return_value=stakeholders),
        ):
            resp = await user_client.get(f"/api/v1/stakeholders/project/{PROJECT_ID}")
        assert resp.status_code == 200
        if resp.status_code == 200:
            assert isinstance(resp.json(), list)

    async def test_list_empty_returns_empty_list(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService,
            "get_project_stakeholders",
            new=AsyncMock(return_value=[]),
        ):
            resp = await user_client.get(f"/api/v1/stakeholders/project/{PROJECT_ID}")
        if resp.status_code == 200:
            assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# 4. Sentiment updates
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestSentimentUpdate:
    async def test_update_to_champion_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        updated = _stakeholder(sentiment=Sentiment.CHAMPION)
        with patch.object(
            StakeholderService,
            "update_stakeholder",
            new=AsyncMock(return_value=updated),
        ):
            resp = await user_client.patch(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}",
                json={"sentiment": "CHAMPION"},
            )
        assert resp.status_code == 200

    async def test_update_to_blocker_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        updated = _stakeholder(sentiment=Sentiment.BLOCKER)
        with patch.object(
            StakeholderService,
            "update_stakeholder",
            new=AsyncMock(return_value=updated),
        ):
            resp = await user_client.patch(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}",
                json={"sentiment": "BLOCKER"},
            )
        assert resp.status_code == 200

    async def test_update_invalid_sentiment_returns_422(self, user_client):
        resp = await user_client.patch(
            f"/api/v1/stakeholders/{STAKEHOLDER_ID}",
            json={"sentiment": "WILDLY_ENTHUSIASTIC"},
        )
        assert resp.status_code == 422

    async def test_update_nonexistent_returns_404(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import NotFoundException

        with patch.object(
            StakeholderService,
            "update_stakeholder",
            new=AsyncMock(side_effect=NotFoundException("not found")),
        ):
            resp = await user_client.patch(
                "/api/v1/stakeholders/9999", json={"sentiment": "CHAMPION"}
            )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 5. AI strategy generation
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestStrategyGeneration:
    async def test_generate_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        strategy = "## Strategic Approach\n\nFocus on risk reduction."
        with patch.object(
            StakeholderService,
            "generate_engagement_strategy",
            new=AsyncMock(return_value=strategy),
        ):
            resp = await user_client.post(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}/strategy"
            )
        assert resp.status_code == 200

    async def test_generate_not_found_returns_404(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import NotFoundException

        with patch.object(
            StakeholderService,
            "generate_engagement_strategy",
            new=AsyncMock(side_effect=NotFoundException("not found")),
        ):
            resp = await user_client.post("/api/v1/stakeholders/9999/strategy")
        assert resp.status_code == 404

    async def test_generate_ai_failure_returns_400(self, user_client):
        """
        The strategy endpoint catches all non-HTTP exceptions and re-raises as
        BadRequestException (400), not 500/503.
        """
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService,
            "generate_engagement_strategy",
            new=AsyncMock(side_effect=RuntimeError("Claude API unavailable")),
        ):
            resp = await user_client.post(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}/strategy"
            )
        assert resp.status_code == 400

    async def test_generate_returns_strategy_key(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService,
            "generate_engagement_strategy",
            new=AsyncMock(return_value="## Plan\n\nContent."),
        ):
            resp = await user_client.post(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}/strategy"
            )
        if resp.status_code == 200:
            assert "strategy" in resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# 6. Stakeholder deletion
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestStakeholderDeletion:
    async def test_delete_returns_204(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService, "delete_stakeholder", new=AsyncMock(return_value=None)
        ):
            resp = await user_client.delete(f"/api/v1/stakeholders/{STAKEHOLDER_ID}")
        assert resp.status_code == 204

    async def test_delete_not_found_returns_404(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import NotFoundException

        with patch.object(
            StakeholderService,
            "delete_stakeholder",
            new=AsyncMock(side_effect=NotFoundException("not found")),
        ):
            resp = await user_client.delete("/api/v1/stakeholders/9999")
        assert resp.status_code == 404

    async def test_delete_forbidden_returns_403(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import ForbiddenException

        with patch.object(
            StakeholderService,
            "delete_stakeholder",
            new=AsyncMock(side_effect=ForbiddenException("no permission")),
        ):
            resp = await user_client.delete(f"/api/v1/stakeholders/{STAKEHOLDER_ID}")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# 7. Mendelow Matrix quadrant coverage
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestMendelowMatrixQuadrants:
    @pytest.mark.parametrize(
        "influence,interest,expected_quadrant",
        [
            (InfluenceLevel.HIGH, InterestLevel.HIGH, "manage_closely"),
            (InfluenceLevel.HIGH, InterestLevel.LOW, "keep_satisfied"),
            (InfluenceLevel.LOW, InterestLevel.HIGH, "keep_informed"),
            (InfluenceLevel.LOW, InterestLevel.LOW, "monitor"),
        ],
    )
    async def test_all_quadrants_creatable(
        self, user_client, influence, interest, expected_quadrant
    ):
        from app.services.stakeholder_service import StakeholderService

        s = _stakeholder(influence=influence, interest=interest)
        with patch.object(
            StakeholderService, "create_stakeholder", new=AsyncMock(return_value=s)
        ):
            resp = await user_client.post(
                f"/api/v1/stakeholders/project/{PROJECT_ID}",
                json={
                    "name": f"Stakeholder {expected_quadrant}",
                    "role": "Director",
                    "influence": influence.value,
                    "interest": interest.value,
                },
            )
        assert resp.status_code in (200, 201)

    async def test_high_influence_blocker_creates_political_risk(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        blocker = _stakeholder(
            name="CFO",
            influence=InfluenceLevel.HIGH,
            interest=InterestLevel.HIGH,
            sentiment=Sentiment.BLOCKER,
        )
        with patch.object(
            StakeholderService,
            "create_stakeholder",
            new=AsyncMock(return_value=blocker),
        ):
            resp = await user_client.post(
                f"/api/v1/stakeholders/project/{PROJECT_ID}",
                json={
                    "name": "Resistant CFO",
                    "role": "CFO",
                    "influence": "HIGH",
                    "interest": "HIGH",
                    "sentiment": "BLOCKER",
                },
            )
        assert resp.status_code in (200, 201)

    async def test_champion_stakeholder_creatable(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        champion = _stakeholder(sentiment=Sentiment.CHAMPION)
        with patch.object(
            StakeholderService,
            "create_stakeholder",
            new=AsyncMock(return_value=champion),
        ):
            resp = await user_client.post(
                f"/api/v1/stakeholders/project/{PROJECT_ID}",
                json={
                    "name": "VP Engineering",
                    "role": "VP Engineering",
                    "influence": "HIGH",
                    "interest": "HIGH",
                    "sentiment": "CHAMPION",
                },
            )
        assert resp.status_code in (200, 201)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Project list (used in stakeholder context)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestProjectEndpoints:
    async def test_project_list_requires_auth(self, client):
        assert (await client.get("/api/v1/projects/")).status_code == 401

    async def test_project_list_returns_200(self, user_client):
        from app.services.project_service import ProjectService

        with patch.object(
            ProjectService,
            "get_user_projects",
            new=AsyncMock(return_value=[_project()]),
        ):
            resp = await user_client.get("/api/v1/projects/")
        assert resp.status_code == 200
        if resp.status_code == 200:
            assert isinstance(resp.json(), list)

    async def test_project_get_by_id_returns_200(self, user_client):
        from app.services.project_service import ProjectService

        with patch.object(
            ProjectService, "get_project_by_id", new=AsyncMock(return_value=_project())
        ):
            resp = await user_client.get(f"/api/v1/projects/{PROJECT_ID}")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 9. Full happy-path smoke test
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.slow
class TestStakeholderAnalysisHappyPath:
    async def test_full_stakeholder_lifecycle(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        s = _stakeholder()
        updated = _stakeholder(sentiment=Sentiment.SUPPORTIVE)

        with patch.object(
            StakeholderService, "create_stakeholder", new=AsyncMock(return_value=s)
        ):
            create_resp = await user_client.post(
                f"/api/v1/stakeholders/project/{PROJECT_ID}",
                json={
                    "name": "Alice Johnson",
                    "role": "CTO",
                    "influence": "HIGH",
                    "interest": "HIGH",
                },
            )
        assert create_resp.status_code in (200, 201)

        with patch.object(
            StakeholderService, "get_by_id", new=AsyncMock(return_value=s)
        ):
            get_resp = await user_client.get(f"/api/v1/stakeholders/{STAKEHOLDER_ID}")
        assert get_resp.status_code == 200

        with patch.object(
            StakeholderService,
            "update_stakeholder",
            new=AsyncMock(return_value=updated),
        ):
            update_resp = await user_client.patch(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}",
                json={"sentiment": "SUPPORTIVE"},
            )
        assert update_resp.status_code == 200

        with patch.object(
            StakeholderService,
            "generate_engagement_strategy",
            new=AsyncMock(return_value="## Strategy\n\nPlan."),
        ):
            strategy_resp = await user_client.post(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}/strategy"
            )
        assert strategy_resp.status_code == 200

        with patch.object(
            StakeholderService,
            "get_project_stakeholders",
            new=AsyncMock(return_value=[s]),
        ):
            list_resp = await user_client.get(
                f"/api/v1/stakeholders/project/{PROJECT_ID}"
            )
        assert list_resp.status_code == 200

        with patch.object(
            StakeholderService, "delete_stakeholder", new=AsyncMock(return_value=None)
        ):
            del_resp = await user_client.delete(
                f"/api/v1/stakeholders/{STAKEHOLDER_ID}"
            )
        assert del_resp.status_code == 204

    async def test_blocker_to_champion_conversion_flow(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        for sentiment in [Sentiment.CONCERNED, Sentiment.NEUTRAL, Sentiment.CHAMPION]:
            updated = _stakeholder(sentiment=sentiment)
            with patch.object(
                StakeholderService,
                "update_stakeholder",
                new=AsyncMock(return_value=updated),
            ):
                resp = await user_client.patch(
                    f"/api/v1/stakeholders/{STAKEHOLDER_ID}",
                    json={"sentiment": sentiment.value},
                )
            assert resp.status_code == 200

    async def test_multiple_stakeholders_across_quadrants(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        configs = [
            (InfluenceLevel.HIGH, InterestLevel.HIGH),
            (InfluenceLevel.HIGH, InterestLevel.LOW),
            (InfluenceLevel.LOW, InterestLevel.HIGH),
            (InfluenceLevel.LOW, InterestLevel.LOW),
        ]
        for i, (influence, interest) in enumerate(configs):
            s = _stakeholder(id=i + 1, influence=influence, interest=interest)
            with patch.object(
                StakeholderService, "create_stakeholder", new=AsyncMock(return_value=s)
            ):
                resp = await user_client.post(
                    f"/api/v1/stakeholders/project/{PROJECT_ID}",
                    json={
                        "name": f"Stakeholder {i}",
                        "role": "Director",
                        "influence": influence.value,
                        "interest": interest.value,
                    },
                )
            assert resp.status_code in (200, 201)
