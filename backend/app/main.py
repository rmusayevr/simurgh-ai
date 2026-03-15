"""
FastAPI application factory and configuration.

This module handles application lifecycle, middleware setup, and global exception handling.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router

from app.core.config import settings
from app.core.exceptions import BaseAppException
from app.core.encryption import verify_encryption_key
from app.core.logging_config import configure_logging
from app.db.session import close_connections, check_database_health, get_pool_status
from app.middleware.maintenance import MaintenanceMiddleware

from app.middleware.rate_limit import (
    RateLimitMiddleware,
    init_redis_pool,
    close_redis_pool,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application lifecycle events.

    Startup:
        - Configures logging
        - Logs application start

    Shutdown:
        - Closes database connection pool
        - Logs graceful shutdown
    """
    # Startup
    configure_logging()
    logger.info("🚀 Application starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"API Version: {settings.API_V1_STR}")
    logger.info(f"Debug Mode: {settings.DEBUG}")

    if settings.RATE_LIMIT_ENABLED:
        await init_redis_pool(app)
        logger.info("✅ Redis rate-limit pool initialised.")

    yield

    # Shutdown
    logger.info("🛑 Application shutting down...")
    await close_connections()
    logger.info("✅ Database connection pool closed.")
    if settings.RATE_LIMIT_ENABLED:
        await close_redis_pool(app)
        logger.info("✅ Redis pool closed.")


def create_application() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.

    Configures:
        - CORS middleware for cross-origin requests
        - Maintenance mode middleware
        - API router with versioned endpoints
        - Global exception handlers

    Returns:
        FastAPI: Configured application instance
    """
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="Simurgh AI is a stakeholder and architecture agent designed to assist software architects in making informed decisions by analyzing project documentation, codebases, and stakeholder input. It provides insights, recommendations, and visualizations to facilitate effective software design and communication.",
        lifespan=lifespan,
        docs_url=f"{settings.API_V1_STR}/docs" if settings.EXPOSE_DOCS else None,
        redoc_url=f"{settings.API_V1_STR}/redoc" if settings.EXPOSE_DOCS else None,
    )

    # Apply middleware in order (last added = first executed)
    _configure_middleware(application)

    # Register API routes
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # Register exception handlers
    _register_exception_handlers(application)

    return application


def _configure_middleware(application: FastAPI) -> None:
    """Configure application middleware."""

    if settings.RATE_LIMIT_ENABLED:
        application.add_middleware(RateLimitMiddleware)

    application.add_middleware(MaintenanceMiddleware)

    origins = [str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS]

    if not origins and settings.is_development:
        origins = ["http://localhost:5173", "http://localhost:3000"]
        logger.warning("⚠️ BACKEND_CORS_ORIGINS was empty! Using local dev defaults.")

    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info(f"✅ CORS correctly enabled for origins: {origins}")
    else:
        logger.error("🚨 No CORS origins configured! Frontend will be blocked.")


def _register_exception_handlers(application: FastAPI) -> None:
    """Register global exception handlers."""

    @application.exception_handler(BaseAppException)
    async def base_app_exception_handler(request: Request, exc: BaseAppException):
        """Handle custom application exceptions."""
        logger.warning(
            f"BaseAppException: {exc.message}",
            extra={
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "detail": getattr(exc, "detail", None)},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """
        Handle Pydantic/FastAPI request validation errors (HTTP 422).

        Converts the raw Pydantic error list into a single human-readable
        message so the frontend can display it directly instead of showing
        the raw JSON array.

        Example: entering a non-email string in the 'Add Member' email field
        previously returned an opaque 422 body; now it returns:
            { "error": "Validation error", "detail": "email: value is not a valid email address" }
        """
        errors = exc.errors()

        # Build a concise, readable message from all validation errors
        messages = []
        for error in errors:
            # 'loc' is a tuple like ('body', 'email') — skip generic prefixes
            field_path = " → ".join(
                str(part)
                for part in error.get("loc", [])
                if part not in ("body", "query", "path")
            )
            msg = error.get("msg", "Invalid value")
            if field_path:
                messages.append(f"{field_path}: {msg}")
            else:
                messages.append(msg)

        readable = "; ".join(messages) if messages else "Invalid request data"

        logger.warning(
            "RequestValidationError",
            extra={
                "path": request.url.path,
                "method": request.method,
                "errors": errors,
            },
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "detail": readable,
            },
        )


# Create application instance
app = create_application()


# Health check endpoint (outside API versioning for monitoring)
@app.get("/health", tags=["System"])
async def health_check():
    """
    Comprehensive health check endpoint.

    Returns:
        dict: Detailed application health status
    """
    # Check components
    db_healthy = await check_database_health()
    encryption_healthy = verify_encryption_key()
    maintenance_status = MaintenanceMiddleware.get_status()

    # Get database pool status (optional)
    try:
        pool_status = await get_pool_status()
    except Exception:
        pool_status = None

    # Determine overall status
    all_healthy = db_healthy and encryption_healthy
    overall_status = "healthy" if all_healthy else "degraded"

    if maintenance_status["enabled"]:
        overall_status = "maintenance"

    response = {
        "status": overall_status,
        "project": settings.PROJECT_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": {
                "status": "up" if db_healthy else "down",
                "healthy": db_healthy,
            },
            "encryption": {
                "status": "up" if encryption_healthy else "down",
                "healthy": encryption_healthy,
            },
            "maintenance_mode": {
                "enabled": maintenance_status["enabled"],
                "cache_age_seconds": maintenance_status["cache_age_seconds"],
            },
        },
    }

    # Add pool status if available
    if pool_status and settings.DEBUG:
        response["components"]["database"]["pool"] = pool_status

    return response
