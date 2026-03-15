"""
Public endpoints (no authentication required).

Provides:
    - System status and health checks
    - Maintenance mode status
    - Registration availability
    - API version info

Used by frontend to check system availability before showing login/register forms.
"""

import structlog
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.core.config import settings as app_settings
from app.services.system_service import SystemService

logger = structlog.get_logger()
router = APIRouter()


@router.get("/status")
async def get_system_status(
    session: AsyncSession = Depends(get_session),
):
    """
    Get public system status.

    Used by frontend to determine:
    - Is the system in maintenance mode?
    - Are new registrations allowed?
    - What version is running?

    No authentication required.

    Returns:
        dict: System status information
    """
    system_service = SystemService(session)
    settings = await system_service.get_settings()

    return {
        "status": "operational" if not settings.maintenance_mode else "maintenance",
        "maintenance_mode": settings.maintenance_mode,
        "allow_registrations": settings.allow_registrations,
        "email_enabled": app_settings.EMAIL_ENABLED,
        "thesis_mode": app_settings.THESIS_MODE,
        "version": "1.0.0",
        "environment": app_settings.ENVIRONMENT,
    }


@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.

    Used by load balancers and monitoring tools.
    Always returns 200 OK if application is running.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "ai-stakeholder-agent",
    }
