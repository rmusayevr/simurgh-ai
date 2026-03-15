"""
API v1 router configuration.

Registers all endpoint routers with appropriate prefixes, tags, and dependencies.

Router Organization:
    - Public endpoints (no auth required)
    - Authentication endpoints
    - Core resources (projects, documents, proposals)
    - Features (debates, stakeholders, integrations)
    - Thesis/Research endpoints
    - Admin endpoints (restricted)
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    auth,
    debates,
    documents,
    evaluation,
    exit_survey,
    experiments,
    projects,
    proposals,
    public,
    stakeholders,
    thesis_metrics,
)
from app.api.v1.endpoints.admin import (
    health as admin_health,
    users as admin_users,
    projects as admin_projects,
    proposals as admin_proposals,
    settings as admin_settings,
    analytics as admin_analytics,
)
from app.api.v1.endpoints.experiment import (
    experiment_dashboard,
    experiment_participants,
    experiment_questionnaires,
    experiment_debates,
    experiment_exit_surveys,
    experiment_rq_summary,
    experiment_manage,
)
from app.api.v1.dependencies import get_current_superuser, get_current_user

# ==================== Main API Router ====================

api_router = APIRouter(
    responses={
        401: {"description": "Unauthorized - Invalid or missing token"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Not Found - Resource doesn't exist"},
        500: {"description": "Internal Server Error"},
    },
)


# ==================== Public Endpoints ====================
# No authentication required

api_router.include_router(
    public.router,
    prefix="/public",
    tags=["Public"],
)


# ==================== Authentication ====================

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)


# ==================== Core Resources ====================
# Require authentication (enforced in individual routers)

api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"],
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"],
)

api_router.include_router(
    proposals.router,
    prefix="/proposals",
    tags=["Proposals"],
)


# ==================== Feature Modules ====================

api_router.include_router(
    debates.router,
    prefix="/debates",
    tags=["Debates"],
)

api_router.include_router(
    stakeholders.router,
    prefix="/stakeholders",
    tags=["Stakeholders"],
)

# ==================== Thesis / Research ====================
# Endpoints for thesis evaluation and data collection

api_router.include_router(
    experiments.router,
    prefix="/experiments",
    tags=["Experiments"],
)

api_router.include_router(
    evaluation.router,
    prefix="/evaluation",
    tags=["Evaluation"],
)

api_router.include_router(
    exit_survey.router,
    prefix="/experiment",
    tags=["Exit Survey"],
)

api_router.include_router(
    thesis_metrics.router,
    prefix="/thesis",
    tags=["Thesis Metrics"],
    dependencies=[Depends(get_current_user)],
)

# ==================== Experiment Data Endpoints ====================
# All require superuser

api_router.include_router(
    experiment_dashboard.router,
    prefix="/experiment-data",
    tags=["Experiment Data"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    experiment_participants.router,
    prefix="/experiment-data",
    tags=["Experiment Data"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    experiment_questionnaires.router,
    prefix="/experiment-data",
    tags=["Experiment Data"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    experiment_debates.router,
    prefix="/experiment-data",
    tags=["Experiment Data"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    experiment_exit_surveys.router,
    prefix="/experiment-data",
    tags=["Experiment Data"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    experiment_rq_summary.router,
    prefix="/experiment-data",
    tags=["Experiment Data"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    experiment_manage.router,
    prefix="/experiment-data",
    tags=["Experiment Data"],
    dependencies=[Depends(get_current_superuser)],
)

# ==================== Admin Endpoints ====================
# Restricted to superusers only

api_router.include_router(
    admin_health.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    admin_users.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    admin_projects.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    admin_proposals.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    admin_settings.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_superuser)],
)

api_router.include_router(
    admin_analytics.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_superuser)],
)
