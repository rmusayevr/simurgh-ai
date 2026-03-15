"""
Experiment Data API Endpoints.

Provides endpoints for managing experiment data, participants, questionnaires,
debates, exit surveys, and research question statistics.

Submodules:
    - experiment_dashboard: Study-level overview metrics
    - experiment_participants: Participant management
    - experiment_questionnaires: Questionnaire response endpoints
    - experiment_debates: Debate session endpoints
    - experiment_exit_surveys: Exit survey endpoints
    - experiment_rq_summary: Research question statistics
    - experiment_manage: Reset and delete endpoints
    - experiment_helpers: Shared utility functions
"""

from app.api.v1.endpoints.experiment import experiment_dashboard
from app.api.v1.endpoints.experiment import experiment_participants
from app.api.v1.endpoints.experiment import experiment_questionnaires
from app.api.v1.endpoints.experiment import experiment_debates
from app.api.v1.endpoints.experiment import experiment_exit_surveys
from app.api.v1.endpoints.experiment import experiment_rq_summary
from app.api.v1.endpoints.experiment import experiment_manage

dashboard = experiment_dashboard
participants = experiment_participants
questionnaires = experiment_questionnaires
debates = experiment_debates
exit_surveys = experiment_exit_surveys
rq_summary = experiment_rq_summary
manage = experiment_manage
