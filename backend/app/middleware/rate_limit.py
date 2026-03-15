"""
Redis sliding-window rate-limiting middleware.

Enforces per-user (authenticated) and per-IP (anonymous) request limits.
The middleware is a no-op when ``RATE_LIMIT_ENABLED=false`` in settings,
so it can be disabled for local development or tests without code changes.

Algorithm:
    Sorted-set sliding window implemented in a single MULTI/EXEC block:
        1. Add the current request timestamp to the set.
        2. Remove all entries older than the window (1 minute).
        3. Count remaining entries.
    If count > limit → 429 Too Many Requests.

Keys and limits:
    rate_limit:user:<user_id>        — authenticated users (JWT Bearer present)
                                       limit: RATE_LIMIT_PER_MINUTE
    rate_limit:auth:<client_ip>      — auth endpoints only (/auth/token, /auth/refresh)
                                       limit: RATE_LIMIT_AUTH_PER_MINUTE
                                       These endpoints never carry a Bearer token so
                                       they MUST NOT fall into the general IP bucket —
                                       otherwise a refresh burst exhausts the login
                                       allowance and vice-versa.
    rate_limit:ip:<client_ip>        — all other anonymous traffic
                                       limit: RATE_LIMIT_ANONYMOUS_PER_MINUTE

Why three buckets?
    Auth endpoints are unauthenticated by definition (they're what issues tokens).
    Without a dedicated bucket they compete with every other anonymous request
    from the same IP.  In Docker / behind a reverse proxy all traffic arrives
    from the same bridge IP, so the general IP bucket fills up almost instantly
    and blocks legitimate logins and token refreshes.

The window expiry is set to 2× the window duration to let Redis auto-clean
sets that are no longer being written to.

Redis connection:
    A single shared async connection pool is created once at application
    startup (via ``init_redis_pool``) and stored on ``app.state.redis``.
    The middleware reads it from there so all Uvicorn workers share one
    pool rather than opening a new connection per request.
"""

import time
import structlog
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Paths that are exempt from rate limiting entirely
_EXEMPT_PREFIXES = (
    "/health",
    "/api/v1/docs",
    "/api/v1/redoc",
    "/openapi.json",
    "/static",
)

# Auth endpoint paths that get their own dedicated bucket.
# These paths never carry a Bearer token — they're the ones that issue tokens.
_AUTH_ENDPOINT_PREFIXES = (
    "/api/v1/auth/token",
    "/api/v1/auth/refresh",
)

# Window duration and key TTL
_WINDOW_SECONDS = 60
_KEY_TTL_SECONDS = _WINDOW_SECONDS * 2


async def init_redis_pool(app):
    """
    Create a shared Redis connection pool and attach it to app.state.

    Call this once during application startup (inside the lifespan context).
    All middleware and dependencies should read from app.state.redis rather
    than opening their own connections.
    """
    import redis.asyncio as aioredis

    pool = aioredis.ConnectionPool.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    app.state.redis = aioredis.Redis(connection_pool=pool)
    logger.info("redis_pool_initialised", url=settings.REDIS_URL)


async def close_redis_pool(app):
    """Close the shared Redis pool on application shutdown."""
    if hasattr(app.state, "redis"):
        await app.state.redis.aclose()
        logger.info("redis_pool_closed")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate-limit middleware backed by a shared Redis pool.

    Three distinct limit tiers (see module docstring for rationale):
      - Authenticated requests:  RATE_LIMIT_PER_MINUTE per user
      - Auth endpoints:          RATE_LIMIT_AUTH_PER_MINUTE per IP
      - Other anonymous traffic: RATE_LIMIT_ANONYMOUS_PER_MINUTE per IP

    Requires ``init_redis_pool`` to be called at startup so that
    ``app.state.redis`` is available. Falls back to fail-open if Redis
    is unavailable, so a Redis outage does not take down the API.
    """

    async def dispatch(self, request: Request, call_next):
        # ── 1. Skip if disabled or exempt path ─────────────────────────────
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        # ── 2. Identify the caller and pick the right bucket ─────────────
        key, limit = await self._get_key_and_limit(request)

        # ── 3. Evaluate the sliding window ──────────────────────────────
        redis_client = getattr(request.app.state, "redis", None)
        allowed, current_count = await self._check_rate_limit(key, limit, redis_client)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                key=key,
                count=current_count,
                limit=limit,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": (
                        f"Rate limit of {limit} requests/minute exceeded. "
                        "Please slow down and retry."
                    ),
                    "retry_after_seconds": _WINDOW_SECONDS,
                },
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )

        # ── 4. Attach rate-limit headers to every response ──────────────
        response = await call_next(request)
        remaining = max(0, limit - current_count)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = f"{_WINDOW_SECONDS}s"
        return response

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract the real client IP, respecting X-Forwarded-For."""
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    @staticmethod
    async def _get_key_and_limit(request: Request):
        """
        Derive the Redis key and applicable limit for this request.

        Priority order:
          1. Auth endpoints (token/refresh) → dedicated IP bucket with
             RATE_LIMIT_AUTH_PER_MINUTE.  These never carry a Bearer token
             so routing them here prevents them from competing with the
             general anonymous IP bucket.
          2. Requests with a valid Bearer token → per-user bucket with
             RATE_LIMIT_PER_MINUTE (the full authenticated limit).
          3. All other anonymous traffic → general IP bucket with
             RATE_LIMIT_ANONYMOUS_PER_MINUTE.
        """
        path = request.url.path

        # ── Tier 1: auth endpoints get their own dedicated bucket ─────────
        if any(path.startswith(p) for p in _AUTH_ENDPOINT_PREFIXES):
            client_ip = RateLimitMiddleware._get_client_ip(request)
            key = f"rate_limit:auth:{client_ip}"
            return key, settings.RATE_LIMIT_AUTH_PER_MINUTE

        # ── Tier 2: authenticated users (Bearer token present) ────────────
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            user_id: Optional[str] = None
            try:
                from jose import jwt as jose_jwt

                token = auth_header.split(" ", 1)[1]
                payload = jose_jwt.decode(
                    token,
                    key="",
                    options={"verify_signature": False, "verify_exp": False},
                    algorithms=[settings.ALGORITHM],
                )
                user_id = payload.get("sub")
            except Exception:
                pass  # Malformed token — fall through to anonymous tier

            if user_id:
                return f"rate_limit:user:{user_id}", settings.RATE_LIMIT_PER_MINUTE

        # ── Tier 3: anonymous traffic ─────────────────────────────────────
        client_ip = RateLimitMiddleware._get_client_ip(request)
        return f"rate_limit:ip:{client_ip}", settings.RATE_LIMIT_ANONYMOUS_PER_MINUTE

    @staticmethod
    async def _check_rate_limit(key: str, limit: int, redis_client):
        """
        Sliding-window check using a Redis sorted set.

        Uses the shared pool from app.state.redis. Falls back to fail-open
        if the client is None or Redis is unavailable.

        Returns:
            (allowed: bool, current_count: int)
        """
        if redis_client is None:
            logger.warning("rate_limit_no_redis_client_fail_open")
            return True, 0

        try:
            now = time.time()
            window_start = now - _WINDOW_SECONDS

            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.zadd(key, {str(now): now})
                pipe.zremrangebyscore(key, "-inf", window_start)
                pipe.zcard(key)
                pipe.expire(key, _KEY_TTL_SECONDS)
                results = await pipe.execute()

            current_count: int = results[2]
            allowed = current_count <= limit
            return allowed, current_count

        except Exception as exc:
            # Redis unavailable → fail-open rather than taking down the API.
            logger.error("rate_limit_redis_error", error=str(exc))
            return True, 0
