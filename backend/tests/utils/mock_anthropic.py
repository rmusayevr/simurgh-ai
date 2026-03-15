"""
Reusable AsyncAnthropic stub for unit tests.

Prevents real API calls while letting you configure responses per-test.
Used across ai_service, debate_service, proposal_service, stakeholder_service.

Usage — simple text response:
    from tests.utils.mock_anthropic import make_anthropic_mock

    def test_something(monkeypatch):
        mock_client = make_anthropic_mock(text="Hello from Claude")
        monkeypatch.setattr("app.services.ai_service.AsyncAnthropic", lambda **kw: mock_client)
        ...

Usage — fixture style (see MockAnthropicFactory):
    @pytest.fixture
    def ai_client(monkeypatch):
        factory = MockAnthropicFactory()
        factory.patch(monkeypatch, "app.services.ai_service.AsyncAnthropic")
        return factory
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock


# ── Usage object ───────────────────────────────────────────────────────────────


def _make_usage(
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
):
    """Build a mock Usage object matching the Anthropic SDK shape."""
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_creation_input_tokens = cache_creation_input_tokens
    usage.cache_read_input_tokens = cache_read_input_tokens
    return usage


# ── Content block helpers ──────────────────────────────────────────────────────


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_name: str, tool_input: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    return block


# ── Message response ───────────────────────────────────────────────────────────


def _make_message_response(
    text: str = "Mock AI response",
    tool_name: str | None = None,
    tool_input: dict | None = None,
    usage_kwargs: dict | None = None,
    stop_reason: str = "end_turn",
):
    """
    Build a mock that looks like `anthropic.types.Message`.

    If `tool_name` is given, the content list will contain a tool_use block
    in addition to (or instead of) the text block.
    """
    content = []
    if text:
        content.append(_make_text_block(text))
    if tool_name:
        content.append(_make_tool_use_block(tool_name, tool_input or {}))

    response = MagicMock()
    response.content = content
    response.stop_reason = stop_reason
    response.usage = _make_usage(**(usage_kwargs or {}))
    response.model = "claude-sonnet-4-20250514"
    return response


# ── Streaming helpers ──────────────────────────────────────────────────────────


async def _async_stream_generator(chunks: list[str]):
    """Yield fake SSE text delta events."""
    for chunk in chunks:
        event = MagicMock()
        event.type = "content_block_delta"
        delta = MagicMock()
        delta.type = "text_delta"
        delta.text = chunk
        event.delta = delta
        yield event

    # Final message_stop event
    stop_event = MagicMock()
    stop_event.type = "message_stop"
    yield stop_event


class _MockStreamContext:
    """
    Async context manager mimicking `client.messages.stream(...)`.

    Usage:
        async with client.messages.stream(...) as stream:
            async for event in stream:
                ...
    """

    def __init__(self, chunks: list[str]):
        self._chunks = chunks

    async def __aenter__(self):
        return _async_stream_generator(self._chunks)

    async def __aexit__(self, *args):
        pass


# ── Main factory ───────────────────────────────────────────────────────────────


def make_anthropic_mock(
    text: str = "Mock AI response",
    tool_name: str | None = None,
    tool_input: dict | None = None,
    stream_chunks: list[str] | None = None,
    usage_kwargs: dict | None = None,
    raise_on_create: Exception | None = None,
) -> MagicMock:
    """
    Build a fully-configured AsyncAnthropic mock.

    Args:
        text:           Text returned by messages.create()
        tool_name:      If set, adds a tool_use block to the response
        tool_input:     Input dict for the tool_use block
        stream_chunks:  If set, messages.stream() yields these strings
        usage_kwargs:   Override token counts in usage (input_tokens, output_tokens, etc.)
        raise_on_create: If set, messages.create() raises this exception

    Returns:
        MagicMock: Configured Anthropic client mock
    """
    client = MagicMock()

    # messages.create()
    if raise_on_create:
        client.messages.create = AsyncMock(side_effect=raise_on_create)
    else:
        response = _make_message_response(
            text=text,
            tool_name=tool_name,
            tool_input=tool_input,
            usage_kwargs=usage_kwargs,
        )
        client.messages.create = AsyncMock(return_value=response)

    # messages.stream() — context manager
    chunks = stream_chunks or [text]
    client.messages.stream = MagicMock(return_value=_MockStreamContext(chunks))

    return client


class MockAnthropicFactory:
    """
    Stateful factory for tests that need to reconfigure the mock mid-test
    or assert call counts/arguments.

    Usage:
        factory = MockAnthropicFactory()
        factory.patch(monkeypatch, "app.services.ai_service.AsyncAnthropic")

        # Reconfigure between calls:
        factory.set_response("New response text")

        # Assert:
        factory.client.messages.create.assert_called_once()
    """

    def __init__(
        self,
        text: str = "Mock AI response",
        usage_kwargs: dict | None = None,
    ):
        self.client = make_anthropic_mock(text=text, usage_kwargs=usage_kwargs)
        self._default_text = text

    def set_response(
        self,
        text: str,
        tool_name: str | None = None,
        tool_input: dict | None = None,
        usage_kwargs: dict | None = None,
    ) -> None:
        """Replace the messages.create return value."""
        response = _make_message_response(
            text=text,
            tool_name=tool_name,
            tool_input=tool_input,
            usage_kwargs=usage_kwargs,
        )
        self.client.messages.create = AsyncMock(return_value=response)

    def set_stream_chunks(self, chunks: list[str]) -> None:
        """Replace the messages.stream context manager."""
        self.client.messages.stream = MagicMock(return_value=_MockStreamContext(chunks))

    def set_side_effect(self, exc: Exception) -> None:
        """Make messages.create raise an exception."""
        self.client.messages.create = AsyncMock(side_effect=exc)

    def patch(self, monkeypatch, target: str) -> None:
        """
        Monkeypatch `target` so that calling it as a constructor returns self.client.

        Args:
            monkeypatch: pytest monkeypatch fixture
            target:      Dotted import path, e.g. "app.services.ai_service.AsyncAnthropic"
        """
        monkeypatch.setattr(target, lambda **kw: self.client)

    @property
    def create_call_count(self) -> int:
        return self.client.messages.create.call_count

    @property
    def last_create_kwargs(self) -> dict[str, Any]:
        """Return the kwargs of the most recent messages.create() call."""
        _, kwargs = self.client.messages.create.call_args
        return kwargs
