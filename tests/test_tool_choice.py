"""Tool-choice emulation: Meta only accepts tool_choice="auto", bolt.diy needs required/named."""
import json
from unittest.mock import AsyncMock

import pytest

from gateway.streaming import stream_chat_completion
from gateway.tool_choice import apply_tool_choice_policy, recover_tool_calls, ToolEnforcement


def _tool(name):
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object", "properties": {}}}}


TOOLS = [_tool("agent_plan"), _tool("project_write_file"), _tool("project_read_file")]


class Stream:
    def __init__(self, chunks):
        self._it = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        pass


def text_chunk(text, finish=None):
    return {"choices": [{"index": 0, "delta": {"content": text}, "finish_reason": finish}]}


def tool_chunk(name, args="{}"):
    return {"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": 0, "id": "call_x", "type": "function", "function": {"name": name, "arguments": args}}]},
        "finish_reason": None}]}


FINISH_TOOLS = {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}
FINISH_STOP = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}


def payload(tool_choice):
    return {
        "model": "muse-spark-1.3",
        "stream": True,
        "tools": TOOLS,
        "tool_choice": tool_choice,
        "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "build a kanban"}],
    }


async def collect(p, client):
    out = []
    async for line in stream_chat_completion(payload=p, client=client, is_auxiliary=False, telemetry_header=""):
        if line.startswith("data: {"):
            out.append(json.loads(line[6:]))
    return out


def names(chunks):
    return [tc["function"]["name"] for c in chunks for ch in c["choices"]
            for tc in (ch.get("delta") or {}).get("tool_calls") or [] if tc.get("function", {}).get("name")]


def test_policy_named_tool_narrows_tools_and_sends_auto():
    kw = {"messages": [{"role": "user", "content": "x"}], "tools": list(TOOLS),
          "tool_choice": {"type": "function", "function": {"name": "agent_plan"}}}
    enf = apply_tool_choice_policy(kw)
    assert kw["tool_choice"] == "auto"
    assert [t["function"]["name"] for t in kw["tools"]] == ["agent_plan"]
    assert enf.kind == "tool" and enf.tool_name == "agent_plan"
    assert "MANDATORY" in kw["messages"][0]["content"]


def test_policy_native_provider_keeps_tool_choice():
    kw = {"messages": [{"role": "user", "content": "x"}], "tools": list(TOOLS), "tool_choice": "required"}
    enf = apply_tool_choice_policy(kw, provider="baseten")
    assert kw["tool_choice"] == "required" and len(kw["tools"]) == 3
    assert enf.kind == "required"


@pytest.mark.asyncio
async def test_final_attempt_escalates_to_fallback_model():
    primary = AsyncMock()
    primary.chat.completions.create = AsyncMock(side_effect=lambda **kw: Stream([text_chunk("prose"), FINISH_STOP]))
    fb = AsyncMock()
    fb.chat.completions.create = AsyncMock(return_value=Stream([tool_chunk("project_write_file"), FINISH_TOOLS]))
    p = payload("required")
    chunks = []
    async for line in stream_chat_completion(payload=p, client=primary, is_auxiliary=False, telemetry_header="",
                                             provider="baseten", fallback=(fb, "muse-spark-1.3", "meta")):
        if line.startswith("data: {"):
            chunks.append(json.loads(line[6:]))
    assert primary.chat.completions.create.await_count == 2
    assert primary.chat.completions.create.call_args.kwargs["tool_choice"] == "required"
    fb_kwargs = fb.chat.completions.create.call_args.kwargs
    assert fb_kwargs["model"] == "muse-spark-1.3" and fb_kwargs["tool_choice"] == "auto"
    assert names(chunks) == ["project_write_file"]


def test_policy_none_drops_tools():
    kw = {"messages": [], "tools": list(TOOLS), "tool_choice": "none"}
    assert apply_tool_choice_policy(kw) is None
    assert "tools" not in kw and "tool_choice" not in kw


@pytest.mark.asyncio
async def test_required_retries_when_model_answers_with_text():
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=[
        Stream([text_chunk("Sure, I'll build it."), FINISH_STOP]),
        Stream([tool_chunk("project_write_file"), FINISH_TOOLS]),
    ])
    chunks = await collect(payload("required"), client)
    assert client.chat.completions.create.await_count == 2
    sent = client.chat.completions.create.call_args_list[0].kwargs
    assert sent["tool_choice"] == "auto"
    assert names(chunks) == ["project_write_file"]
    # the text-only first attempt must never reach bolt.diy
    assert not any("Sure" in (ch.get("delta") or {}).get("content", "") for c in chunks for ch in c["choices"])
    assert sum(1 for c in chunks for ch in c["choices"] if "role" in (ch.get("delta") or {})) == 1


@pytest.mark.asyncio
async def test_required_recovers_json_printed_in_markdown():
    printed = '```json\n{"name": "project_write_file", "arguments": {"path": "a.txt", "content": "hi"}}\n```'
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=Stream([text_chunk(printed), FINISH_STOP]))
    chunks = await collect(payload("required"), client)
    assert client.chat.completions.create.await_count == 1
    assert names(chunks) == ["project_write_file"]
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"


@pytest.mark.asyncio
async def test_text_before_tool_call_is_kept_and_streamed():
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=Stream([
        text_chunk("Planning the board."), tool_chunk("agent_plan"), FINISH_TOOLS]))
    chunks = await collect(payload({"type": "function", "function": {"name": "agent_plan"}}), client)
    assert client.chat.completions.create.await_count == 1
    assert names(chunks) == ["agent_plan"]
    assert chunks[0]["choices"][0]["delta"]["content"] == "Planning the board."


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts_and_passes_text_through():
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=lambda **kw: Stream([text_chunk("no tools"), FINISH_STOP]))
    chunks = await collect(payload("required"), client)
    assert client.chat.completions.create.await_count == 3
    assert any((ch.get("delta") or {}).get("content") == "no tools" for c in chunks for ch in c["choices"])


def test_recover_rejects_unknown_tool_and_wrong_named_tool():
    enf = ToolEnforcement("tool", "agent_plan")
    assert recover_tool_calls('{"name": "rm_rf", "arguments": {}}', TOOLS, enf) == []
    assert recover_tool_calls('{"name": "project_write_file", "arguments": {}}', TOOLS, enf) == []
    assert recover_tool_calls('<tool_call>{"name": "agent_plan", "parameters": {"steps": []}}</tool_call>',
                              TOOLS, enf)[0]["function"]["name"] == "agent_plan"
