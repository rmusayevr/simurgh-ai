"""
Maintenance mode middleware.

Blocks incoming requests when system is in maintenance mode.
Maintenance state is cached and refreshed periodically from database.

Features:
    - Configurable bypass paths (admin, health checks)
    - Periodic state refresh (reduces DB queries)
    - Graceful error handling
    - Request logging for monitoring
"""

import time
import structlog
from typing import List

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.db.session import async_session_factory

logger = structlog.get_logger(__name__)


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce maintenance mode.

    When maintenance mode is active, blocks all requests except:
        - Admin endpoints (for toggling maintenance mode)
        - Health checks
        - Authentication endpoints
        - Static assets
        - API documentation

    Maintenance state is cached and refreshed every 30 seconds
    to minimize database load.
    """

    # Class-level state (shared across all instances)
    _maintenance_mode: bool = False
    _last_check: float = 0
    _check_interval: int = 30  # seconds
    _cache_lock: bool = False  # Simple lock to prevent concurrent DB queries

    # Configurable bypass paths
    BYPASS_PATHS: List[str] = [
        "/health",  # Health check endpoint
        "/api/v1/admin",  # Admin endpoints
        "/api/v1/auth",  # Authentication endpoints
        "/api/v1/system/status",  # Public status endpoint
        "/docs",  # API documentation
        "/redoc",  # Alternative API docs
        "/openapi.json",  # OpenAPI schema
        "/static",  # Static assets
    ]

    async def dispatch(self, request: Request, call_next):
        """
        Process incoming request and check maintenance mode.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response: Either maintenance error or normal response
        """
        # Check if path should bypass maintenance mode
        if self._should_bypass(request.url.path):
            return await call_next(request)

        # Refresh maintenance state from database (with caching)
        await self._refresh_maintenance_state()

        # Block request if in maintenance mode
        if self._maintenance_mode:
            logger.info(
                "maintenance_blocked_request",
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else "unknown",
            )

            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "detail": "System is currently undergoing maintenance. Please try again later.",
                    "maintenance": True,
                    "retry_after": 300,  # Suggest retry after 5 minutes
                },
                headers={
                    "Retry-After": "300",  # Standard HTTP header
                    "X-Maintenance-Mode": "true",
                },
            )

        # Normal request processing
        return await call_next(request)

    def _should_bypass(self, path: str) -> bool:
        """
        Check if request path should bypass maintenance mode.

        Args:
            path: Request URL path

        Returns:
            bool: True if path should bypass maintenance check
        """
        return any(path.startswith(bypass_path) for bypass_path in self.BYPASS_PATHS)

    async def _refresh_maintenance_state(self) -> None:
        """
        Refresh maintenance mode state from database.

        Uses time-based caching to reduce database load:
            - Only queries database every 30 seconds
            - Uses simple lock to prevent concurrent queries
            - Gracefully handles database errors

        Fallback behavior on error:
            - Disables maintenance mode (fail-open)
            - Logs error for monitoring
        """
        current_time = time.time()

        # Check if cache is still valid
        if current_time - self._last_check < self._check_interval:
            return

        # Simple lock to prevent concurrent DB queries
        if self._cache_lock:
            return

        self._cache_lock = True

        try:
            # Check config first (no DB query needed)
            if hasattr(settings, "MAINTENANCE_MODE"):
                type(self)._maintenance_mode = settings.MAINTENANCE_MODE
                type(self)._last_check = current_time
                logger.debug(
                    "maintenance_mode_from_config", enabled=self._maintenance_mode
                )
                return

            # Otherwise, check database
            async with async_session_factory() as session:
                # Lazy import to avoid circular dependencies
                from app.services.system_service import SystemService

                service = SystemService(session)
                system_settings = await service.get_settings()

                # Update state
                old_state = type(self)._maintenance_mode
                type(self)._maintenance_mode = system_settings.maintenance_mode
                type(self)._last_check = current_time

                # Log state changes
                if old_state != self._maintenance_mode:
                    logger.warning(
                        "maintenance_mode_changed",
                        old_state=old_state,
                        new_state=self._maintenance_mode,
                    )
                else:
                    logger.debug(
                        "maintenance_mode_refreshed", enabled=self._maintenance_mode
                    )

        except Exception as e:
            logger.error(
                "maintenance_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

            # Fail-open: disable maintenance mode on error
            # This ensures service availability if database is down
            type(self)._maintenance_mode = False
            type(self)._last_check = current_time

        finally:
            self._cache_lock = False

    @classmethod
    def enable_maintenance_mode(cls) -> None:
        """
        Manually enable maintenance mode.

        Useful for testing or emergency maintenance.

        Example:
            >>> MaintenanceMiddleware.enable_maintenance_mode()
        """
        cls._maintenance_mode = True
        cls._last_check = time.time()
        logger.warning("maintenance_mode_manually_enabled")

    @classmethod
    def disable_maintenance_mode(cls) -> None:
        """
        Manually disable maintenance mode.

        Example:
            >>> MaintenanceMiddleware.disable_maintenance_mode()
        """
        cls._maintenance_mode = False
        cls._last_check = time.time()
        logger.info("maintenance_mode_manually_disabled")

    @classmethod
    def get_status(cls) -> dict:
        """
        Get current maintenance mode status.

        Returns:
            dict: Status information

        Example:
            >>> status = MaintenanceMiddleware.get_status()
            >>> print(status)
            {'enabled': False, 'last_check': 1708185600, 'cache_age': 15}
        """
        current_time = time.time()
        return {
            "enabled": cls._maintenance_mode,
            "last_check": cls._last_check,
            "cache_age_seconds": int(current_time - cls._last_check),
            "check_interval": cls._check_interval,
        }

    @classmethod
    def invalidate_cache(cls) -> None:
        """
        Force cache invalidation on next request.

        Useful when maintenance mode is toggled via admin endpoint.

        Example:
            >>> MaintenanceMiddleware.invalidate_cache()
        """
        cls._last_check = 0
        logger.debug("maintenance_cache_invalidated")
