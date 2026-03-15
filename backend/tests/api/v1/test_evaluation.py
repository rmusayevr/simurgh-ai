"""Phase 7 — API: Evaluation / questionnaire endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4
from app.models.questionnaire import ExperimentCondition

BASE = "/api/v1/evaluation"


def _q_payload(participant_id=1):
    return {
        "participant_id": participant_id,
        "scenario_id": 1,
        "condition": "BASELINE",
        "trust_overall": 5,
        "risk_awareness": 4,
        "technical_soundness": 5,
        "balance": 4,
        "actionability": 5,
        "completeness": 4,
        "strengths": "Good",
        "concerns": "OK",
        "trust_reasoning": "Solid",
        "time_to_complete_seconds": 120,
        "order_in_session": 1,
    }


class TestSubmitQuestionnaire:
    async def test_submit_returns_201(self, user_client_no_db):
        from app.services.questionnaire_service import QuestionnaireService

        stub = MagicMock()
        stub.id = uuid4()
        stub.participant_id = 1
        stub.scenario_id = 1
        stub.condition = ExperimentCondition.BASELINE
        stub.trust_overall = 5
        stub.risk_awareness = 4
        stub.technical_soundness = 5
        stub.balance = 4
        stub.actionability = 5
        stub.completeness = 4
        stub.strengths = "Good"
        stub.concerns = "OK"
        stub.trust_reasoning = "Solid"
        stub.persona_consistency = None
        stub.debate_value = None
        stub.most_convincing_persona = None
        stub.time_to_complete_seconds = 120
        stub.order_in_session = 1
        stub.session_id = None
        stub.condition_order = None
        stub.is_valid = True
        stub.quality_note = None
        stub.submitted_at = datetime(2024, 1, 1)

        with patch.object(
            QuestionnaireService, "submit_response", new=AsyncMock(return_value=stub)
        ):
            resp = await user_client_no_db.post(f"{BASE}/responses", json=_q_payload())
        assert resp.status_code == 201

    async def test_submit_likert_out_of_range_returns_422(self, user_client_no_db):
        resp = await user_client_no_db.post(
            f"{BASE}/responses", json={**_q_payload(), "trust_overall": 8}
        )
        assert resp.status_code == 422

    async def test_submit_likert_below_range_returns_422(self, user_client_no_db):
        resp = await user_client_no_db.post(
            f"{BASE}/responses", json={**_q_payload(), "trust_overall": 0}
        )
        assert resp.status_code == 422

    async def test_submit_requires_auth(self, client):
        assert (
            await client.post(f"{BASE}/responses", json=_q_payload())
        ).status_code == 401


class TestListResponses:
    async def test_list_returns_200(self, user_client_no_db):
        from app.services.questionnaire_service import QuestionnaireService

        with patch.object(
            QuestionnaireService, "get_all_responses", new=AsyncMock(return_value=[])
        ):
            resp = await user_client_no_db.get(f"{BASE}/responses")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_requires_auth(self, client):
        assert (await client.get(f"{BASE}/responses")).status_code == 401


class TestGetStatistics:
    async def test_statistics_returns_200(self, user_client_no_db):
        from app.services.questionnaire_service import QuestionnaireService

        summary = {
            "total_responses": 0,
            "baseline_n": 0,
            "multiagent_n": 0,
            "baseline_mean_trust": None,
            "multiagent_mean_trust": None,
        }
        with patch.object(
            QuestionnaireService,
            "calculate_summary_statistics",
            new=AsyncMock(return_value=summary),
        ):
            resp = await user_client_no_db.get(f"{BASE}/statistics")
        assert resp.status_code == 200

    async def test_statistics_requires_auth(self, client):
        assert (await client.get(f"{BASE}/statistics")).status_code == 401
