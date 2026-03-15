"""
Async test helpers.

Provides:
    - collect_sse_stream: Drain a Server-Sent Events response into a list of strings
    - run_async:          Run a coroutine synchronously (for non-async test contexts)
    - timeout_after:      Async context manager that fails a test if it takes too long
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator


async def collect_sse_stream(response) -> list[str]:
    """
    Drain an HTTPX streaming response containing Server-Sent Events.

    Parses lines of the form:
        data: {"type": "text", "content": "..."}
    and returns the "content" values in order.

    Ignores comment lines (starting with ":") and blank lines.

    Args:
        response: httpx.Response with iter_lines() support (streaming)

    Returns:
        list[str]: Ordered list of content strings from data events

    Usage:
        async with client.stream("GET", "/api/v1/debates/1/stream") as resp:
            chunks = await collect_sse_stream(resp)
        assert len(chunks) > 0
    """
    chunks: list[str] = []

    async for line in response.aiter_lines():
        line = line.strip()

        if not line or line.startswith(":"):
            continue  # blank line or SSE comment

        if line.startswith("data:"):
            raw = line[len("data:") :].strip()

            if raw == "[DONE]":
                break

            try:
                payload = json.loads(raw)
                if "content" in payload:
                    chunks.append(payload["content"])
                elif "text" in payload:
                    chunks.append(payload["text"])
                else:
                    # Fallback: store the whole payload as a string
                    chunks.append(raw)
            except json.JSONDecodeError:
                # Plain-text SSE (not JSON) — store as-is
                chunks.append(raw)

    return chunks


async def collect_async_generator(gen: AsyncIterator) -> list:
    """
    Exhaust an async generator and return all items as a list.

    Usage:
        items = await collect_async_generator(service.stream_response(...))
    """
    return [item async for item in gen]


def run_async(coro) -> any:
    """
    Run a coroutine synchronously.

    Useful in non-async test setup code or conftest factories.
    Not needed if asyncio_mode = "auto" is set (just await directly).

    Usage:
        result = run_async(some_async_function(arg))
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an existing event loop (e.g., Jupyter, pytest-asyncio)
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class timeout_after:
    """
    Async context manager that fails the test if the block takes too long.

    Usage:
        async with timeout_after(seconds=2):
            await some_slow_operation()
    """

    def __init__(self, seconds: float = 5.0):
        self.seconds = seconds
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    @staticmethod
    async def run(coro, seconds: float = 5.0):
        """
        Run a coroutine with a timeout, raising AssertionError if it exceeds it.

        Usage:
            result = await timeout_after.run(my_coro(), seconds=3)
        """
        try:
            return await asyncio.wait_for(coro, timeout=seconds)
        except asyncio.TimeoutError:
            raise AssertionError(
                f"Test timed out after {seconds}s — operation took too long"
            )
