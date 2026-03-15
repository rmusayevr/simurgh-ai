"""
Admin - Health and monitoring endpoints.

GET /admin/health
GET /admin/health/worker
GET /admin/logs
"""

import structlog
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.core.config import settings as app_settings
from app.core.celery_app import celery_app
from app.core.exceptions import BadRequestException
from app.models.user import User
from app.models.project import Project
from app.models.proposal import Proposal, ProposalStatus
from app.models.stakeholder import Stakeholder
from app.models.chunk import DocumentChunk

logger = structlog.get_logger()
router = APIRouter()


async def check_database_health(session: AsyncSession) -> bool:
    """Extracted helper so tests can patch it."""
    try:
        (await session.exec(select(func.count()).select_from(User))).one()
        return True
    except Exception:
        return False


@router.get("/health")
async def get_system_health(
    session: AsyncSession = Depends(get_session),
):
    """
    Get comprehensive system health status.

    Returns counts, queue depth, recent activity, and system status.
    """
    log = logger.bind(operation="system_health")

    try:
        total_users = (await session.exec(select(func.count()).select_from(User))).one()
        total_projects = (
            await session.exec(select(func.count()).select_from(Project))
        ).one()
        total_proposals = (
            await session.exec(select(func.count()).select_from(Proposal))
        ).one()
        processing_proposals = (
            await session.exec(
                select(func.count())
                .select_from(Proposal)
                .where(Proposal.status == ProposalStatus.PROCESSING)
            )
        ).one()
        total_stakeholders = (
            await session.exec(select(func.count()).select_from(Stakeholder))
        ).one()
        total_chunks = (
            await session.exec(select(func.count()).select_from(DocumentChunk))
        ).one()

        from redis import Redis

        try:
            redis_client = Redis.from_url(str(app_settings.REDIS_URL))
            queue_length = redis_client.llen("celery")
            redis_client.close()
            redis_client.connection_pool.disconnect()
        except Exception:
            queue_length = -1

        from app.core.celery_app import celery_app

        try:
            i = celery_app.control.inspect()
            ping_result = i.ping()
            workers_online = len(ping_result) if ping_result else 0
        except Exception:
            workers_online = -1

        system_status = "healthy"
        if workers_online == -1 or queue_length == -1:
            system_status = "degraded"
        if workers_online == 0:
            system_status = "unhealthy"

        response = {
            "status": system_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": (
                "connected" if await check_database_health(session) else "error"
            ),
            "counts": {
                "users": total_users,
                "projects": total_projects,
                "proposals": total_proposals,
                "processing_proposals": processing_proposals,
                "stakeholders": total_stakeholders,
                "chunks": total_chunks,
            },
            "queue": {
                "pending_tasks": queue_length,
            },
            "workers": {
                "online": workers_online,
            },
        }

        log.info("system_health_retrieved", status=system_status)
        return response

    except Exception as e:
        logger.error("system_health_failed", error=str(e))
        return {
            "error": "Failed to retrieve system health",
            "system_status": "error",
        }


@router.get("/health/worker")
async def get_worker_health():
    """
    Check Celery worker status.

    Returns online status, worker count, and worker details.
    """
    try:
        i = celery_app.control.inspect()
        ping = i.ping()

        if not ping:
            return {
                "status": "offline",
                "workers": 0,
                "message": "No workers responding",
            }

        return {
            "status": "online",
            "workers": len(ping),
            "details": ping,
        }

    except Exception as e:
        logger.error("worker_health_check_failed", error=str(e))
        return {
            "status": "error",
            "workers": 0,
            "message": "Could not connect to Celery",
            "error": str(e),
        }


@router.get("/logs")
async def get_system_logs(
    lines: int = Query(default=100, ge=1, le=1000),
):
    """
    Retrieve recent application logs.

    Args:
        lines: Number of log lines to retrieve (1-1000)

    Returns:
        dict: Log lines
    """
    log_file = "logs/app.log"

    if not os.path.exists(log_file):
        return {
            "logs": ["Log file not found. File logging may not be enabled."],
            "file_exists": False,
        }

    try:
        with open(log_file, "r") as f:
            content = f.readlines()
            last_lines = content[-lines:]
            return {
                "logs": [line.strip() for line in last_lines],
                "total_lines": len(content),
                "returned_lines": len(last_lines),
            }
    except Exception as e:
        logger.error("log_retrieval_failed", error=str(e))
        raise BadRequestException(f"Failed to read logs: {str(e)}")
