"""
Celery application configuration for background task processing.
"""

import structlog
from celery import Celery
from celery.signals import setup_logging, worker_ready, worker_shutdown
from kombu import Queue, Exchange

from app.core.config import settings
from app.core.logging_config import configure_logging

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "stakeholder_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

default_exchange = Exchange("default", type="direct")
vectorization_exchange = Exchange("vectorization", type="direct")
proposals_exchange = Exchange("proposals", type="direct")

CELERY_QUEUES = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("vectorization", vectorization_exchange, routing_key="vectorization"),
    Queue("proposals", proposals_exchange, routing_key="proposals"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
    task_queues=CELERY_QUEUES,
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    task_routes={
        "generate_proposal_content": {"queue": "proposals"},
        "process_document_embeddings": {"queue": "vectorization"},
    },
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    task_acks_on_failure_or_timeout=True,
    task_reject_on_worker_lost=True,
    result_backend_transport_options={"visibility_timeout": 3600},
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

celery_app.conf.imports = [
    "app.services.vector_service",
    "app.services.proposal_service",
]


@setup_logging.connect
def configure_celery_logging(*args, **kwargs):
    configure_logging()
    logger.info(
        "celery_logging_configured",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    logger.info(
        "celery_worker_ready",
        hostname=sender.hostname,
        environment=settings.ENVIRONMENT,
    )


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    logger.info("celery_worker_shutdown", hostname=sender.hostname)


class BaseTask(celery_app.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "task_failed", task_id=task_id, task_name=self.name, exception=str(exc)
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info("task_success", task_id=task_id, task_name=self.name)
        super().on_success(retval, task_id, args, kwargs)


celery_app.Task = BaseTask


@celery_app.task(name="celery.health_check", bind=True)
def health_check_task(self):
    return {
        "status": "healthy",
        "worker_id": self.request.id,
        "hostname": self.request.hostname,
    }
