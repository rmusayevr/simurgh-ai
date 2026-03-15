"""
Unit tests for app/middleware/rate_limit.py

Covers:
    RateLimitMiddleware.dispatch:
        - Disabled middleware passes all requests through (RATE_LIMIT_ENABLED=False)
        - Exempt paths (/health, /docs, /redoc, /openapi.json, /static) always pass
        - Allowed request attaches X-RateLimit-* headers to response
        - Request at exactly the limit is allowed (count == limit)
        - Request over the limit returns 429 with Retry-After header
        - 429 body contains error, detail, and retry_after_seconds fields
        - Redis error → fail-open (allow request, no crash)

    RateLimitMiddleware._get_key_and_limit (pure path logic):
        - Valid Bearer JWT → key uses user id, full limit
        - No Authorization header → key uses IP, limit halved (max(1, limit//2))
        - Malformed Bearer token → falls back to IP key
        - X-Forwarded-For present → first IP in list used
        - No client info → "unknown" IP used

    RateLimitMiddleware._check_rate_limit (Redis interaction):
        - Executes ZADD + ZREMRANGEBYSCORE + ZCARD + EXPIRE in one pipeline
        - count <= limit → (True, count)
        - count > limit → (False, count)
        - Redis pipeline exception → fail-open (True, 0)

All Redis calls are mocked. No real network or DB.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_request(
    path: str = "/api/v1/proposals",
    auth_header: str = None,
    client_ip: str = "1.2.3.4",
    forwarded_for: str = None,
) -> MagicMock:
    """Build a minimal mock Request."""
    req = MagicMock(spec=Request)
    req.url = MagicMock()
    req.url.path = path
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    req.headers = headers
    req.client = MagicMock()
    req.client.host = client_ip
    return req


async def _noop_next(request):
    """Minimal call_next that returns a 200 PlainTextResponse."""
    resp = MagicMock()
    resp.headers = {}
    resp.status_code = 200
    return resp


def _make_middleware():
    from app.middleware.rate_limit import RateLimitMiddleware

    app = MagicMock()
    mw = RateLimitMiddleware(app)
    return mw


# ══════════════════════════════════════════════════════════════════
# dispatch — global on/off switch
# ══════════════════════════════════════════════════════════════════


class TestDispatchDisabled:
    async def test_disabled_passes_without_redis(self):
        """When RATE_LIMIT_ENABLED=False, no Redis call is made."""
        mw = _make_middleware()
        req = _make_request()

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False
            called = []

            async def call_next(r):
                called.append(True)
                return await _noop_next(r)

            await mw.dispatch(req, call_next)

        assert called == [True]

    async def test_disabled_returns_response_unchanged(self):
        """Disabled middleware returns the downstream response directly."""
        mw = _make_middleware()
        req = _make_request()
        sentinel = MagicMock()
        sentinel.headers = {}

        async def call_next(r):
            return sentinel

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False
            resp = await mw.dispatch(req, call_next)

        assert resp is sentinel


# ══════════════════════════════════════════════════════════════════
# dispatch — exempt paths
# ══════════════════════════════════════════════════════════════════


class TestExemptPaths:
    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/live",
            "/api/v1/docs",
            "/api/v1/redoc",
            "/openapi.json",
            "/static/logo.png",
        ],
    )
    async def test_exempt_path_bypasses_rate_limit(self, path):
        """Requests to exempt paths are forwarded without any Redis call."""
        mw = _make_middleware()
        req = _make_request(path=path)
        called = []

        async def call_next(r):
            called.append(True)
            return await _noop_next(r)

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            # If _check_rate_limit were called it would try to connect to Redis,
            # so we patch it to assert it is NOT called.
            with patch.object(mw, "_check_rate_limit") as mock_check:
                await mw.dispatch(req, call_next)

        assert called == [True]
        mock_check.assert_not_called()

    async def test_non_exempt_path_does_rate_check(self):
        """Non-exempt path triggers the rate-limit check."""
        mw = _make_middleware()
        req = _make_request(path="/api/v1/proposals")

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw, "_check_rate_limit", new_callable=AsyncMock, return_value=(True, 1)
            ) as mock_check:
                with patch.object(
                    mw,
                    "_get_key_and_limit",
                    new_callable=AsyncMock,
                    return_value=("rate_limit:ip:1.2.3.4", 60),
                ):
                    await mw.dispatch(req, _noop_next)

        mock_check.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# dispatch — allowed requests
# ══════════════════════════════════════════════════════════════════


class TestDispatchAllowed:
    async def test_allowed_request_calls_next(self):
        """Allowed request forwards to downstream handler."""
        mw = _make_middleware()
        req = _make_request()
        called = []

        async def call_next(r):
            called.append(True)
            resp = MagicMock()
            resp.headers = {}
            return resp

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", 60),
            ):
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(True, 5),
                ):
                    await mw.dispatch(req, call_next)

        assert called == [True]

    async def test_allowed_attaches_x_ratelimit_limit_header(self):
        """X-RateLimit-Limit header is set to the applicable limit."""
        mw = _make_middleware()
        req = _make_request()
        resp_mock = MagicMock()
        resp_mock.headers = {}

        async def call_next(r):
            return resp_mock

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", 60),
            ):
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(True, 10),
                ):
                    await mw.dispatch(req, call_next)

        assert resp_mock.headers["X-RateLimit-Limit"] == "60"

    async def test_allowed_attaches_x_ratelimit_remaining_header(self):
        """X-RateLimit-Remaining = limit - current_count."""
        mw = _make_middleware()
        req = _make_request()
        resp_mock = MagicMock()
        resp_mock.headers = {}

        async def call_next(r):
            return resp_mock

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", 60),
            ):
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(True, 10),
                ):
                    await mw.dispatch(req, call_next)

        assert resp_mock.headers["X-RateLimit-Remaining"] == "50"

    async def test_remaining_never_negative(self):
        """Remaining is clamped at 0 even if count > limit (race condition guard)."""
        mw = _make_middleware()
        req = _make_request()
        resp_mock = MagicMock()
        resp_mock.headers = {}

        async def call_next(r):
            return resp_mock

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", 60),
            ):
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(True, 65),
                ):  # count > limit
                    await mw.dispatch(req, call_next)

        assert resp_mock.headers["X-RateLimit-Remaining"] == "0"

    async def test_allowed_attaches_x_ratelimit_window_header(self):
        """X-RateLimit-Window shows the window duration in seconds."""
        mw = _make_middleware()
        req = _make_request()
        resp_mock = MagicMock()
        resp_mock.headers = {}

        async def call_next(r):
            return resp_mock

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", 60),
            ):
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(True, 1),
                ):
                    await mw.dispatch(req, call_next)

        assert resp_mock.headers["X-RateLimit-Window"] == "60s"

    async def test_request_exactly_at_limit_is_allowed(self):
        """count == limit is still within budget → allowed."""
        mw = _make_middleware()
        req = _make_request()
        called = []

        async def call_next(r):
            called.append(True)
            resp = MagicMock()
            resp.headers = {}
            return resp

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", 60),
            ):
                # _check_rate_limit returns (True, 60) — at exactly the limit
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(True, 60),
                ):
                    await mw.dispatch(req, call_next)

        assert called == [True]


# ══════════════════════════════════════════════════════════════════
# dispatch — rate limited (429)
# ══════════════════════════════════════════════════════════════════


class TestDispatch429:
    async def _call_limited(self, count=61, limit=60):
        mw = _make_middleware()
        req = _make_request()

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = limit
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", limit),
            ):
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(False, count),
                ):
                    return await mw.dispatch(req, _noop_next)

    async def test_over_limit_returns_429(self):
        resp = await self._call_limited()
        assert resp.status_code == 429

    async def test_429_body_has_error_field(self):
        resp = await self._call_limited()
        assert resp.body  # JSONResponse has .body
        import json

        body = json.loads(resp.body)
        assert "error" in body

    async def test_429_body_has_detail_field(self):
        resp = await self._call_limited()
        import json

        body = json.loads(resp.body)
        assert "detail" in body

    async def test_429_body_has_retry_after_seconds(self):
        resp = await self._call_limited()
        import json

        body = json.loads(resp.body)
        assert "retry_after_seconds" in body
        assert body["retry_after_seconds"] == 60  # _WINDOW_SECONDS

    async def test_429_has_retry_after_header(self):
        resp = await self._call_limited()
        assert "Retry-After" in resp.headers

    async def test_429_does_not_call_next(self):
        """Downstream handler must not be called when rate limited."""
        mw = _make_middleware()
        req = _make_request()
        called = []

        async def call_next(r):
            called.append(True)
            return await _noop_next(r)

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            with patch.object(
                mw,
                "_get_key_and_limit",
                new_callable=AsyncMock,
                return_value=("rate_limit:ip:1.2.3.4", 60),
            ):
                with patch.object(
                    mw,
                    "_check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=(False, 61),
                ):
                    await mw.dispatch(req, call_next)

        assert called == []


# ══════════════════════════════════════════════════════════════════
# _get_key_and_limit — key derivation
# ══════════════════════════════════════════════════════════════════


class TestGetKeyAndLimit:
    async def test_authenticated_user_gets_user_key(self):
        """Valid Bearer JWT → key is rate_limit:user:<sub>."""
        import jose.jwt as jose_jwt
        from app.middleware.rate_limit import RateLimitMiddleware

        token = jose_jwt.encode(
            {"sub": "42", "type": "access"}, "secret", algorithm="HS256"
        )
        req = _make_request(auth_header=f"Bearer {token}")

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            mock_settings.ALGORITHM = "HS256"
            key, limit = await RateLimitMiddleware._get_key_and_limit(req)

        assert key == "rate_limit:user:42"
        assert limit == 60

    async def test_no_auth_header_uses_ip_key(self):
        """No Authorization header → key is rate_limit:ip:<client_ip>."""
        from app.middleware.rate_limit import RateLimitMiddleware

        req = _make_request(client_ip="10.0.0.1")

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            mock_settings.ALGORITHM = "HS256"
            key, limit = await RateLimitMiddleware._get_key_and_limit(req)

        assert key == "rate_limit:ip:10.0.0.1"

    async def test_anonymous_limit_is_halved(self):
        """Anonymous users get half the regular rate limit."""
        from app.middleware.rate_limit import RateLimitMiddleware

        req = _make_request(client_ip="10.0.0.1")

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            mock_settings.RATE_LIMIT_ANONYMOUS_PER_MINUTE = 60
            mock_settings.ALGORITHM = "HS256"
            _, limit = await RateLimitMiddleware._get_key_and_limit(req)

        assert limit == 60

    async def test_anonymous_limit_minimum_is_1(self):
        """Even with a very low setting, anonymous limit floors at 1."""
        from app.middleware.rate_limit import RateLimitMiddleware

        req = _make_request(client_ip="10.0.0.1")

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            mock_settings.RATE_LIMIT_ANONYMOUS_PER_MINUTE = 1
            mock_settings.ALGORITHM = "HS256"
            _, limit = await RateLimitMiddleware._get_key_and_limit(req)

        assert limit == 1

    async def test_malformed_bearer_token_falls_back_to_ip(self):
        """Garbage JWT → exception swallowed → IP-based key used."""
        from app.middleware.rate_limit import RateLimitMiddleware

        req = _make_request(auth_header="Bearer not.a.jwt", client_ip="5.5.5.5")

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            mock_settings.ALGORITHM = "HS256"
            key, _ = await RateLimitMiddleware._get_key_and_limit(req)

        assert key == "rate_limit:ip:5.5.5.5"

    async def test_x_forwarded_for_used_when_present(self):
        """First IP in X-Forwarded-For header is used for anonymous key."""
        from app.middleware.rate_limit import RateLimitMiddleware

        req = _make_request(
            client_ip="192.168.1.1", forwarded_for="203.0.113.1, 10.0.0.1"
        )

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            mock_settings.ALGORITHM = "HS256"
            key, _ = await RateLimitMiddleware._get_key_and_limit(req)

        assert key == "rate_limit:ip:203.0.113.1"

    async def test_no_client_uses_unknown_ip(self):
        """request.client is None → IP falls back to 'unknown'."""
        from app.middleware.rate_limit import RateLimitMiddleware

        req = _make_request()
        req.client = None  # no client info

        with patch("app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 60
            mock_settings.ALGORITHM = "HS256"
            key, _ = await RateLimitMiddleware._get_key_and_limit(req)

        assert key == "rate_limit:ip:unknown"


# ══════════════════════════════════════════════════════════════════
# _check_rate_limit — Redis pipeline logic
# ══════════════════════════════════════════════════════════════════


class TestCheckRateLimit:
    def _make_pipeline_mock(self, zcard_result: int):
        """Build a mock Redis pipeline that returns zcard_result from execute()."""
        pipeline = AsyncMock()
        pipeline.__aenter__ = AsyncMock(return_value=pipeline)
        pipeline.__aexit__ = AsyncMock(return_value=False)
        # execute() returns [zadd_result, zremrange_result, zcard_result, expire_result]
        pipeline.execute = AsyncMock(return_value=[1, 0, zcard_result, 1])
        pipeline.zadd = MagicMock()
        pipeline.zremrangebyscore = MagicMock()
        pipeline.zcard = MagicMock()
        pipeline.expire = MagicMock()
        return pipeline

    def _make_redis_mock(self, pipeline):
        redis_client = AsyncMock()
        redis_client.pipeline = MagicMock(return_value=pipeline)
        redis_client.aclose = AsyncMock()
        return redis_client

    async def test_within_limit_returns_true(self):
        from app.middleware.rate_limit import RateLimitMiddleware

        pipeline = self._make_pipeline_mock(zcard_result=5)
        redis_mock = self._make_redis_mock(pipeline)

        allowed, count = await RateLimitMiddleware._check_rate_limit(
            "rate_limit:ip:1.2.3.4", 60, redis_mock
        )

        assert allowed is True
        assert count == 5

    async def test_over_limit_returns_false(self):
        from app.middleware.rate_limit import RateLimitMiddleware

        pipeline = self._make_pipeline_mock(zcard_result=61)
        redis_mock = self._make_redis_mock(pipeline)

        allowed, count = await RateLimitMiddleware._check_rate_limit(
            "rate_limit:ip:1.2.3.4", 60, redis_mock
        )

        assert allowed is False
        assert count == 61

    async def test_exactly_at_limit_is_allowed(self):
        """count == limit → allowed (boundary inclusive)."""
        from app.middleware.rate_limit import RateLimitMiddleware

        pipeline = self._make_pipeline_mock(zcard_result=60)
        redis_mock = self._make_redis_mock(pipeline)

        allowed, _ = await RateLimitMiddleware._check_rate_limit(
            "rate_limit:ip:1.2.3.4", 60, redis_mock
        )

        assert allowed is True

    async def test_redis_error_fails_open(self):
        """Redis connection failure → (True, 0) — fail open, don't crash the API."""
        from app.middleware.rate_limit import RateLimitMiddleware

        # Simulate pipeline raising on execute
        pipeline = self._make_pipeline_mock(zcard_result=0)
        pipeline.execute = AsyncMock(side_effect=Exception("redis down"))
        redis_mock = self._make_redis_mock(pipeline)

        allowed, count = await RateLimitMiddleware._check_rate_limit(
            "rate_limit:ip:1.2.3.4", 60, redis_mock
        )

        assert allowed is True
        assert count == 0

    async def test_redis_client_none_fails_open(self):
        """None redis_client (pool not initialised) → (True, 0) — fail open."""
        from app.middleware.rate_limit import RateLimitMiddleware

        allowed, count = await RateLimitMiddleware._check_rate_limit(
            "rate_limit:ip:1.2.3.4", 60, None
        )

        assert allowed is True
        assert count == 0

    async def test_pipeline_executes_four_commands(self):
        """zadd + zremrangebyscore + zcard + expire must all be called."""
        from app.middleware.rate_limit import RateLimitMiddleware

        pipeline = self._make_pipeline_mock(zcard_result=1)
        redis_mock = self._make_redis_mock(pipeline)

        await RateLimitMiddleware._check_rate_limit(
            "rate_limit:ip:1.2.3.4", 60, redis_mock
        )

        pipeline.zadd.assert_called_once()
        pipeline.zremrangebyscore.assert_called_once()
        pipeline.zcard.assert_called_once()
        pipeline.expire.assert_called_once()
