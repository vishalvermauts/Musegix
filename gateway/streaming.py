import inspect
import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from fastapi import Request
from openai import AsyncOpenAI

from gateway.tool_choice import (
    MAX_ENFORCEMENT_ATTEMPTS,
    apply_tool_choice_policy,
    kwargs_for_attempt,
    recover_tool_calls,
    strip_private,
)

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger("gateway.streaming")

_clients: Dict[str, AsyncOpenAI] = {}
_custom_client: Optional[AsyncOpenAI] = None


def get_upstream_client(provider: str = "meta") -> AsyncOpenAI:
    """Return the appropriate client based on provider and available keys."""
    global _custom_client
    if _custom_client is not None:
        return _custom_client

    provider = (provider or "meta").lower()
    if provider in _clients:
        return _clients[provider]

    meta_key = os.getenv("META_API_KEY")
    baseten_key = os.getenv("BASETEN_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if provider == "meta" and meta_key:
        base_url = os.getenv("META_BASE_URL", "https://api.meta.ai/v1")
        client = AsyncOpenAI(api_key=meta_key, base_url=base_url)
    elif provider == "baseten" and baseten_key:
        base_url = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")
        client = AsyncOpenAI(api_key=baseten_key, base_url=base_url)
    elif meta_key:
        base_url = os.getenv("META_BASE_URL", "https://api.meta.ai/v1")
        client = AsyncOpenAI(api_key=meta_key, base_url=base_url)
    elif baseten_key:
        base_url = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")
        client = AsyncOpenAI(api_key=baseten_key, base_url=base_url)
    elif openai_key:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        client = AsyncOpenAI(api_key=openai_key, base_url=base_url)
    else:
        client = AsyncOpenAI(api_key="sk-dummy-key", base_url=None)

    _clients[provider] = client
    return client


def set_upstream_client(client: Optional[AsyncOpenAI]) -> None:
    global _custom_client
    _custom_client = client


def is_auxiliary_request(payload: dict) -> bool:
    """
    Determines whether a request is an auxiliary bolt.diy call
    (prompt enhancement, chat title/summary, context ranking)
    rather than a primary code generation request.
    """
    if payload.get("is_auxiliary"):
        return True

    messages = payload.get("messages", [])
    if not messages:
        return False

    # bolt.diy's summary / context-selection / enhancer calls never send tools, while every
    # agent coding step does. The main system prompt also embeds a "CHAT SUMMARY:" section,
    # which used to misclassify real coding steps as auxiliary (skipping triage and pruning).
    if payload.get("tools"):
        return False

    auxiliary_patterns = [
        "prompt engineer",
        "enhance prompt",
        "refine prompt",
        "improve prompt",
        "prompt enhancer",
        "generate a title",
        "generate a concise title",
        "create a title",
        "short title",
        "summarize the conversation",
        "summarize this conversation",
        "summarize the chat",
        "chat summary",
        "conversation title",
        "suggest a title",
        # Exact bolt.diy auxiliary system prompts (app/lib/.server/llm/create-summary.ts,
        # select-context.ts, app/routes/api.enhancer.ts)
        "summarize the work till now",
        "updatecontextbuffer",
        "current context buffer",
        "professional prompt engineer",
        "senior software principal architect",
    ]

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and "text" in part
            )
        if isinstance(content, str):
            # Auxiliary system prompts state their job up front; only the opening counts, so
            # sections deep inside the main coding prompt cannot trigger a match.
            lower_content = content.lower()[:800] if msg.get("role") == "system" else content.lower()
            if any(pattern in lower_content for pattern in auxiliary_patterns):
                return True

    return False


def get_default_telemetry_banner(
    tier: str = "MODERATE",
    target_model: str = "muse-spark-1.3",
    triage_ms: Optional[float] = None,
    selected_tokens: Optional[int] = None,
    raw_tokens: Optional[int] = None,
    stale_memories: Optional[int] = None,
    tool_raw: Optional[int] = None,
    tool_kept: Optional[int] = None,
    impact: Optional[list] = None,
) -> str:
    """
    Constructs the telemetry banner for primary coding completions.
    Zero mock heuristics: unmeasured metrics show 'n/a'.
    """
    triage_str = f"{triage_ms:.1f}ms ONNX CPU" if triage_ms is not None else "n/a"
    if selected_tokens is not None and raw_tokens is not None and raw_tokens > 0:
        reduction_pct = ((raw_tokens - selected_tokens) / raw_tokens) * 100
        pruned_str = f"`{selected_tokens}` tokens vs `{raw_tokens}` raw ({reduction_pct:.1f}% pruned)"
    elif selected_tokens is not None:
        pruned_str = f"`{selected_tokens}` tokens (raw: n/a)"
    else:
        pruned_str = "n/a"

    stale_str = f"{stale_memories} stale memories detected" if stale_memories is not None else "n/a"

    import json as _json

    status = {
        "tier": tier,
        "model": target_model,
        "triageMs": round(triage_ms, 1) if triage_ms is not None else None,
        "selectedTokens": selected_tokens,
        "rawTokens": raw_tokens,
        "prunedPct": round(((raw_tokens - selected_tokens) / raw_tokens) * 100, 1)
        if selected_tokens is not None and raw_tokens and raw_tokens > 0 else None,
        "staleMemories": stale_memories,
        "toolRaw": tool_raw,
        "toolKept": tool_kept,
        "toolPrunedPct": round(((tool_raw - tool_kept) / tool_raw) * 100, 1) if tool_raw and tool_kept is not None and tool_raw > 0 else None,
        "impact": impact or [],
    }
    return (
        f"```musegix-status\n{_json.dumps(status)}\n```\n\n"
    )


async def stream_chat_completion(
    payload: dict,
    request: Optional[Request] = None,
    target_model: Optional[str] = None,
    client: Optional[AsyncOpenAI] = None,
    is_auxiliary: Optional[bool] = None,
    telemetry_header: Optional[str] = None,
    provider: str = "meta",
    fallback: Optional[Tuple[AsyncOpenAI, str, str]] = None,
    extra_banner: Optional[str] = None,
    on_tool_call: Optional[Callable[[str, dict], None]] = None,
) -> AsyncGenerator[str, None]:
    """Proxy one chat completion as SSE.

    ``fallback`` = (client, model, provider) used for the final attempt when a required tool call
    is still missing, e.g. escalating from the Baseten open-weights tier to Muse Spark 1.3.
    """
    req_id = f"chatcmpl-mgx-{int(time.time() * 1000)}"

    if not target_model:
        model_param = payload.get("model")
        if not model_param or model_param == "musecontext-auto":
            target_model = os.getenv("DEFAULT_MODEL", "muse-spark-1.3")
        else:
            target_model = model_param

    if client is None:
        client = get_upstream_client()

    if is_auxiliary is None:
        is_auxiliary = is_auxiliary_request(payload)

    messages = payload.get("messages", [])
    has_tools = bool(payload.get("tools"))
    emitted_role = False
    stats: Dict[str, Any] = {"finish": None, "usage": None, "args": {}, "names": {}}

    def to_dict(chunk: Any) -> Dict[str, Any]:
        if hasattr(chunk, "model_dump"):
            return chunk.model_dump(exclude_none=True)
        if isinstance(chunk, dict):
            return dict(chunk)
        return json.loads(str(chunk))

    def render(chunk_dict: Dict[str, Any]) -> Optional[str]:
        """Normalize one chunk (stable id, exactly one role delta) and serialize it, or drop no-ops."""
        nonlocal emitted_role
        chunk_dict["id"] = req_id
        _track(stats, chunk_dict)
        choices = chunk_dict.get("choices") or []
        chunk_dict["choices"] = choices
        for choice in choices:
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            if "role" in delta:
                if emitted_role:
                    delta.pop("role", None)
                else:
                    delta["role"] = str(delta["role"]).strip() or "assistant"
            elif not emitted_role:
                delta["role"] = "assistant"
        if choices:
            c0 = choices[0]
            if not c0.get("delta") and c0.get("finish_reason") is None and not chunk_dict.get("usage"):
                return None
            if any("role" in (c.get("delta") or {}) for c in choices):
                emitted_role = True
        return f"data: {json.dumps(chunk_dict)}\n\n"

    def synthetic(delta: Dict[str, Any], finish_reason: Optional[str] = None) -> Dict[str, Any]:
        return {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": target_model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

    # 1. Telemetry banner. Plain-text requests always get it; agent (tool) requests only on the
    #    first step of a user turn, so it shows once per prompt instead of once per tool step.
    #    Text next to a tool call is valid for the AI SDK; only a step with NO matching tool call
    #    violates a required tool_choice, and that is enforced below.
    show_banner = not is_auxiliary and (not has_tools or _is_first_agent_step(messages))
    if show_banner:
        if telemetry_header is None:
            telemetry_header = get_default_telemetry_banner(target_model=target_model)
        if telemetry_header:
            out = render(synthetic({"role": "assistant", "content": telemetry_header}))
            if out:
                yield out
    elif extra_banner and not is_auxiliary:
        out = render(synthetic({"role": "assistant", "content": extra_banner}))
        if out:
            yield out
    elif telemetry_header:
        clean_comment = telemetry_header.strip().replace("\n", " ")
        yield f": telemetry: {clean_comment}\n\n"

    # 2. Upstream request. Meta accepts only tool_choice="auto"; see gateway/tool_choice.py.
    create_kwargs: Dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": payload.get("temperature", 0.2),
        "max_tokens": payload.get("max_tokens", 4096),
    }
    for key in ["tools", "tool_choice", "response_format", "stop", "top_p", "presence_penalty", "frequency_penalty"]:
        if key in payload and payload[key] is not None:
            create_kwargs[key] = payload[key]
    base_kwargs = dict(create_kwargs)
    enforcement = apply_tool_choice_policy(create_kwargs, provider)

    upstream = None
    try:
        if enforcement is None:
            upstream = await client.chat.completions.create(**strip_private(create_kwargs))
            async for chunk in upstream:
                if request is not None and await request.is_disconnected():
                    break
                out = render(to_dict(chunk))
                if out:
                    yield out
        else:
            for attempt in range(MAX_ENFORCEMENT_ATTEMPTS):
                attempt_client = client
                if fallback is not None and attempt == MAX_ENFORCEMENT_ATTEMPTS - 1:
                    attempt_client, fb_model, fb_provider = fallback
                    fb_kwargs = dict(base_kwargs, model=fb_model)
                    fb_enf = apply_tool_choice_policy(fb_kwargs, fb_provider) or enforcement
                    attempt_kwargs = kwargs_for_attempt(fb_kwargs, fb_enf, attempt)
                    logger.warning(f"Escalating to {fb_provider}/{fb_model} for the final tool-call attempt")
                else:
                    attempt_kwargs = kwargs_for_attempt(create_kwargs, enforcement, attempt)
                upstream = await attempt_client.chat.completions.create(**attempt_kwargs)
                buffered: List[Dict[str, Any]] = []
                text_parts: List[str] = []
                satisfied = False
                disconnected = False
                try:
                    async for chunk in upstream:
                        if request is not None and await request.is_disconnected():
                            disconnected = True
                            break
                        cd = to_dict(chunk)
                        if satisfied:
                            out = render(cd)
                            if out:
                                yield out
                            continue
                        for choice in cd.get("choices") or []:
                            delta = choice.get("delta") or {}
                            text_parts.append(delta.get("content") or "")
                            for tc in delta.get("tool_calls") or []:
                                if enforcement.satisfied_by((tc.get("function") or {}).get("name")):
                                    satisfied = True
                        buffered.append(cd)
                        if satisfied:
                            # Tool call confirmed: release held text and stream the rest live.
                            for held in buffered:
                                out = render(held)
                                if out:
                                    yield out
                            buffered = []
                finally:
                    await _close(upstream)
                    upstream = None

                if satisfied or disconnected:
                    break

                recovered = recover_tool_calls("".join(text_parts), attempt_kwargs.get("tools"), enforcement)
                if recovered:
                    logger.info(f"Recovered {len(recovered)} tool call(s) printed as text (attempt {attempt + 1})")
                    deltas = [dict(call, index=i) for i, call in enumerate(recovered)]
                    for piece in (synthetic({"tool_calls": deltas}), synthetic({}, finish_reason="tool_calls")):
                        out = render(piece)
                        if out:
                            yield out
                    for held in buffered:
                        if held.get("usage") and not held.get("choices"):
                            out = render(held)
                            if out:
                                yield out
                    break

                if attempt + 1 < MAX_ENFORCEMENT_ATTEMPTS:
                    logger.warning(
                        f"{attempt_kwargs.get('model')} returned no {enforcement.kind} tool call "
                        f"({enforcement.tool_name or 'any'}); retry {attempt + 2}/{MAX_ENFORCEMENT_ATTEMPTS}. "
                        f"Text was: {''.join(text_parts)[:200]!r}"
                    )
                    continue

                logger.error("Upstream never produced the required tool call; passing response through")
                for held in buffered:
                    out = render(held)
                    if out:
                        yield out

    except Exception as e:
        logger.error(f"Error in stream_chat_completion: {e}\n{traceback.format_exc()}")
        error_delta = {"content": f"\n\n> ❌ **Musegix Gateway Error**: {type(e).__name__} - {str(e)}"}
        out = render(synthetic(error_delta, finish_reason="stop"))
        if out:
            yield out

    finally:
        await _close(upstream)
        _log_stats(target_model, payload, stats)
        _notify_tool_calls(stats, on_tool_call)

    yield "data: [DONE]\n\n"


def _track(stats: Dict[str, Any], chunk_dict: Dict[str, Any]) -> None:
    if chunk_dict.get("usage"):
        stats["usage"] = chunk_dict["usage"]
    for choice in chunk_dict.get("choices") or []:
        if choice.get("finish_reason"):
            stats["finish"] = choice["finish_reason"]
        for tc in (choice.get("delta") or {}).get("tool_calls") or []:
            i = tc.get("index", 0)
            fn = tc.get("function") or {}
            if fn.get("name"):
                stats["names"][i] = fn["name"]
            stats["args"][i] = stats["args"].get(i, "") + (fn.get("arguments") or "")


def _notify_tool_calls(stats: Dict[str, Any], on_tool_call: Optional[Callable[[str, dict], None]]) -> None:
    """Hand each completed tool call to the caller as soon as the model finishes generating it.

    Runs before bolt executes the call, so the symbol index learns a file at generation time.
    """
    if on_tool_call is None:
        return
    for i, name in list(stats.get("names", {}).items()):
        raw = stats.get("args", {}).get(i, "")
        try:
            args = json.loads(raw or "{}")
        except (ValueError, TypeError):
            if name == "project_write_file":
                logger.warning(f"[toolcheck] project_write_file arguments are not valid JSON ({len(raw)} chars): {raw[:80]!r}")
            continue
        if name == "project_write_file" and not isinstance(args.get("content"), str):
            logger.warning(f"[toolcheck] project_write_file missing content; keys={sorted(args.keys())} ({len(raw)} chars)")
        if isinstance(args, dict):
            try:
                on_tool_call(name, args)
            except Exception as e:  # never break the stream for an index error
                logger.warning(f"on_tool_call failed for {name}: {e}")


def _log_stats(model: str, payload: Dict[str, Any], stats: Dict[str, Any]) -> None:
    """One line per request: lets you see truncated tool arguments or missing tool calls at a glance."""
    calls = []
    for i, name in stats["names"].items():
        raw = stats["args"].get(i, "")
        try:
            json.loads(raw or "{}")
            calls.append(f"{name}:ok")
        except ValueError:
            calls.append(f"{name}:UNPARSEABLE({len(raw)} chars)")
    usage = stats["usage"] or {}
    logger.info(
        f"[stream] model={model} max_tokens={payload.get('max_tokens')} "
        f"tool_choice={str(payload.get('tool_choice'))[:60]} finish={stats['finish']} "
        f"completion_tokens={usage.get('completion_tokens')} tool_calls={calls}"
    )


def _is_first_agent_step(messages: List[Dict[str, Any]]) -> bool:
    """True when the latest non-system message is the user's prompt (no tool results yet this turn)."""
    for msg in reversed(messages or []):
        if not isinstance(msg, dict) or msg.get("role") == "system":
            continue
        return msg.get("role") == "user"
    return False


async def _close(upstream: Any) -> None:
    if upstream is not None and hasattr(upstream, "close"):
        try:
            res = upstream.close()
            if inspect.isawaitable(res):
                await res
        except Exception:
            pass
