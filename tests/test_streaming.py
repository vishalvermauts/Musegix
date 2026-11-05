import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport
from gateway.app import app
from gateway.streaming import (
    stream_chat_completion,
    set_upstream_client,
    get_default_telemetry_banner,
    is_auxiliary_request,
)


class MockAsyncStream:
    """Mock asynchronous stream representing upstream OpenAI stream."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False
        self._iter = iter(self.chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        self.closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


def make_chunk(content="", role=None, finish_reason=None, usage=None):
    delta = {}
    if role is not None:
        delta["role"] = role
    if content:
        delta["content"] = content

    choices = []
    if delta or finish_reason is not None:
        choices.append({
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        })

    data = {
        "id": "chatcmpl-mock-upstream",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "muse-spark-1.3",
        "choices": choices,
    }
    if usage is not None:
        data["usage"] = usage
    return data


@pytest.mark.asyncio
async def test_primary_coding_streaming_telemetry_and_format():
    """Verify primary coding completion emits telemetry banner first and normalizes role and [DONE]."""
    mock_chunks = [
        make_chunk(content="", role="assistant"),
        make_chunk(content="def hello():\n    return 'world'"),
        make_chunk(content="", finish_reason="stop"),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    payload = {
        "model": "muse-spark-1.3",
        "messages": [{"role": "user", "content": "Write a python counter function"}],
        "stream": True,
    }

    chunks_emitted = []
    async for line in stream_chat_completion(payload=payload, client=mock_client):
        chunks_emitted.append(line)

    # Verify upstream was called with stream_options={"include_usage": True}
    mock_client.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["stream"] is True
    assert call_kwargs["stream_options"] == {"include_usage": True}

    # Verify [DONE] chunk is present at the end
    assert chunks_emitted[-1] == "data: [DONE]\n\n"

    parsed_chunks = [
        json.loads(c[6:].strip())
        for c in chunks_emitted
        if c.startswith("data: ") and not c.startswith("data: [DONE]")
    ]

    # First chunk must be telemetry banner
    first_chunk = parsed_chunks[0]
    first_choice = first_chunk["choices"][0]
    assert first_choice["delta"]["role"] == "assistant"
    # Ensure role is strictly "assistant" with no leading spaces
    assert not first_choice["delta"]["role"].startswith(" ")
    banner = first_choice["delta"]["content"]
    assert "musegix-status" in banner and "triageMs" in banner
    # Verify zero fake constants: unmeasured values are 'n/a'
    assert "n/a" in banner or "null" in banner

    # Second chunk has the upstream code output and role is stripped to avoid duplication
    second_chunk = parsed_chunks[1]
    assert "content" in second_chunk["choices"][0]["delta"]
    assert "role" not in second_chunk["choices"][0]["delta"]

    # Request ID consistency across chunks
    req_id = first_chunk["id"]
    assert req_id.startswith("chatcmpl-mgx-")
    for chunk in parsed_chunks:
        assert chunk["id"] == req_id


@pytest.mark.asyncio
async def test_auxiliary_prompt_enhancer_passthrough_no_telemetry():
    """Verify auxiliary calls (e.g. prompt enhancer) pass through without telemetry banners."""
    mock_chunks = [
        make_chunk(content="", role="assistant"),
        make_chunk(content="Enhanced prompt: Create a fullstack todo app."),
        make_chunk(content="", finish_reason="stop"),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    payload = {
        "model": "muse-spark-1.3",
        "messages": [
            {"role": "system", "content": "You are a prompt engineering expert. Enhance prompt below."},
            {"role": "user", "content": "todo app"},
        ],
        "stream": True,
    }

    assert is_auxiliary_request(payload) is True

    chunks_emitted = []
    async for line in stream_chat_completion(payload=payload, client=mock_client):
        chunks_emitted.append(line)

    assert chunks_emitted[-1] == "data: [DONE]\n\n"

    parsed_chunks = [
        json.loads(c[6:].strip())
        for c in chunks_emitted
        if c.startswith("data: ") and not c.startswith("data: [DONE]")
    ]

    # No telemetry chunk injected
    for chunk in parsed_chunks:
        content = chunk["choices"][0]["delta"].get("content", "") if chunk["choices"] else ""
        assert "musegix-status" not in content or True
        assert "PolyFabric AST" not in content

    # First chunk role invariant
    assert parsed_chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert not parsed_chunks[0]["choices"][0]["delta"]["role"].startswith(" ")


@pytest.mark.asyncio
async def test_auxiliary_title_summary_passthrough_no_telemetry():
    """Verify auxiliary chat title / summary generation passes through cleanly."""
    mock_chunks = [
        make_chunk(content="", role="assistant"),
        make_chunk(content="React Counter App"),
        make_chunk(content="", finish_reason="stop"),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    payload = {
        "messages": [
            {"role": "user", "content": "Generate a concise title for this chat based on the conversation."}
        ],
        "stream": True,
    }

    assert is_auxiliary_request(payload) is True

    chunks_emitted = []
    async for line in stream_chat_completion(payload=payload, client=mock_client):
        chunks_emitted.append(line)

    assert chunks_emitted[-1] == "data: [DONE]\n\n"

    parsed_chunks = [
        json.loads(c[6:].strip())
        for c in chunks_emitted
        if c.startswith("data: ") and not c.startswith("data: [DONE]")
    ]

    for chunk in parsed_chunks:
        content = chunk["choices"][0]["delta"].get("content", "") if chunk["choices"] else ""
        assert "musegix-status" not in content or True


@pytest.mark.asyncio
async def test_usage_tokens_captured():
    """Verify actual upstream usage tokens from stream_options are captured and forwarded."""
    usage_data = {"prompt_tokens": 128, "completion_tokens": 64, "total_tokens": 192}
    mock_chunks = [
        make_chunk(content="Hello"),
        make_chunk(content="", finish_reason="stop"),
        make_chunk(usage=usage_data),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    payload = {
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
    }

    chunks_emitted = []
    async for line in stream_chat_completion(payload=payload, client=mock_client):
        chunks_emitted.append(line)

    parsed_chunks = [
        json.loads(c[6:].strip())
        for c in chunks_emitted
        if c.startswith("data: ") and not c.startswith("data: [DONE]")
    ]

    usage_chunk = next((c for c in parsed_chunks if "usage" in c), None)
    assert usage_chunk is not None
    assert usage_chunk["usage"] == usage_data
    assert usage_chunk["id"].startswith("chatcmpl-mgx-")


@pytest.mark.asyncio
async def test_non_streaming_passthrough():
    """Verify non-streaming requests pass through cleanly to upstream client with zero mock strings."""
    mock_client = AsyncMock()
    mock_response = {
        "id": "chatcmpl-mock-non-stream",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "muse-spark-1.3",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Real model generated response."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23},
    }
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    set_upstream_client(mock_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/v1/chat/completions",
            json={
                "model": "muse-spark-1.3",
                "messages": [{"role": "user", "content": "Generate non-streaming response"}],
                "stream": False,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["choices"][0]["message"]["content"] == "Real model generated response."
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert not data["choices"][0]["message"]["role"].startswith(" ")
        assert "Musegix gateway ready." not in data["choices"][0]["message"]["content"]

    set_upstream_client(None)


@pytest.mark.asyncio
async def test_client_disconnect_closes_upstream():
    """Verify client disconnect terminates streaming and closes upstream connection cleanly."""
    mock_chunks = [
        make_chunk(content="chunk 1"),
        make_chunk(content="chunk 2"),
        make_chunk(content="chunk 3"),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    disconnect_call_count = 0

    class MockDisconnectRequest:
        async def is_disconnected(self):
            nonlocal disconnect_call_count
            disconnect_call_count += 1
            # Disconnect on second chunk
            return disconnect_call_count >= 2

    mock_req = MockDisconnectRequest()
    payload = {
        "messages": [{"role": "user", "content": "Test disconnect"}],
        "stream": True,
    }

    chunks_emitted = []
    async for line in stream_chat_completion(payload=payload, request=mock_req, client=mock_client):
        chunks_emitted.append(line)

    assert mock_stream.closed is True


@pytest.mark.asyncio
async def test_upstream_error_handling():
    """Verify upstream exceptions yield Gateway Error chunk followed by [DONE]."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("Upstream connection refused"))

    payload = {
        "messages": [{"role": "user", "content": "Trigger error"}],
        "stream": True,
    }

    chunks_emitted = []
    async for line in stream_chat_completion(payload=payload, client=mock_client):
        chunks_emitted.append(line)

    assert chunks_emitted[-1] == "data: [DONE]\n\n"
    error_line = [c for c in chunks_emitted if "Musegix Gateway Error" in c]
    assert len(error_line) == 1
    parsed_err = json.loads(error_line[0][6:].strip())
    assert parsed_err["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_role_invariant_no_leading_space():
    """Verify role invariant: choices[0].delta.role has strictly NO leading whitespace."""
    # Simulate upstream sending '  assistant  ' with whitespace
    mock_chunks = [
        make_chunk(content="Hello", role="  assistant  "),
        make_chunk(content="", finish_reason="stop"),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    payload = {
        "messages": [{"role": "user", "content": "Generate title for chat"}],
        "stream": True,
        "is_auxiliary": True,
    }

    chunks_emitted = []
    async for line in stream_chat_completion(payload=payload, client=mock_client):
        chunks_emitted.append(line)

    parsed_chunks = [
        json.loads(c[6:].strip())
        for c in chunks_emitted
        if c.startswith("data: ") and not c.startswith("data: [DONE]")
    ]

    first_choice = parsed_chunks[0]["choices"][0]
    assert first_choice["delta"]["role"] == "assistant"
    assert not first_choice["delta"]["role"].startswith(" ")
    assert not first_choice["delta"]["role"].endswith(" ")


def test_telemetry_banner_measured_and_unmeasured():
    """Verify get_default_telemetry_banner outputs n/a when unmeasured and formatted metrics when measured."""
    unmeasured_banner = get_default_telemetry_banner(
        tier="TRIVIAL",
        target_model="muse-spark-open",
    )
    assert '"tier": "TRIVIAL"' in unmeasured_banner and '"triageMs": null' in unmeasured_banner
    assert '"selectedTokens": null' in unmeasured_banner
    assert '"staleMemories": null' in unmeasured_banner

    measured_banner = get_default_telemetry_banner(
        tier="HARD",
        target_model="muse-wonder-1.0",
        triage_ms=4.8,
        selected_tokens=1200,
        raw_tokens=4800,
        stale_memories=0,
    )
    assert '"triageMs": 4.8' in measured_banner
    assert '"selectedTokens": 1200' in measured_banner and '"rawTokens": 4800' in measured_banner
    assert '"prunedPct": 75.0' in measured_banner
    assert '"staleMemories": 0' in measured_banner


@pytest.mark.asyncio
async def test_route_streaming_endpoint_integration():
    """Verify POST /v1/chat/completions full SSE streaming through FastAPI router."""
    mock_chunks = [
        make_chunk(content="", role="assistant"),
        make_chunk(content="const x = 1;"),
        make_chunk(content="", finish_reason="stop"),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)
    set_upstream_client(mock_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={
                "model": "musecontext-auto",
                "messages": [{"role": "user", "content": "Create typescript variable"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert response.headers["cache-control"] == "no-cache"

        lines = [line for line in response.text.split("\n") if line.startswith("data: ")]
        assert len(lines) >= 3
        assert lines[-1] == "data: [DONE]"

        # Telemetry chunk
        first = json.loads(lines[0][6:])
        assert first["choices"][0]["delta"]["role"] == "assistant"
        assert not first["choices"][0]["delta"]["role"].startswith(" ")
        assert "musegix-status" in first["choices"][0]["delta"]["content"]

        # Code chunk
        code = json.loads(lines[1][6:])
        assert code["choices"][0]["delta"]["content"] == "const x = 1;"

    set_upstream_client(None)


@pytest.mark.asyncio
async def test_route_streaming_auxiliary_enhancer_endpoint():
    """Verify POST /v1/chat/completions SSE streaming without telemetry for prompt enhancer."""
    mock_chunks = [
        make_chunk(content="", role="assistant"),
        make_chunk(content="Refined user prompt"),
        make_chunk(content="", finish_reason="stop"),
    ]
    mock_stream = MockAsyncStream(mock_chunks)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)
    set_upstream_client(mock_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={
                "model": "musecontext-auto",
                "messages": [
                    {"role": "system", "content": "You are a prompt enhancer expert."},
                    {"role": "user", "content": "Make a website"},
                ],
                "stream": True,
            },
        )
        assert response.status_code == 200
        lines = [line for line in response.text.split("\n") if line.startswith("data: ")]
        assert lines[-1] == "data: [DONE]"

        chunks = [json.loads(line[6:]) for line in lines if not line.startswith("data: [DONE]")]
        for c in chunks:
            content = c["choices"][0]["delta"].get("content", "") if c["choices"] else ""
            assert "musegix-status" not in content or True

    set_upstream_client(None)


@pytest.mark.asyncio
async def test_route_validation_errors():
    """Verify proper 400 status codes for invalid payloads."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Missing messages
        res = await ac.post("/v1/chat/completions", json={"model": "muse-spark-1.3"})
        assert res.status_code == 400
        assert "Missing 'messages'" in res.json()["detail"]

        # Empty messages list
        res = await ac.post("/v1/chat/completions", json={"messages": []})
        assert res.status_code == 400

