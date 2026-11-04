import inspect
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, Optional
from fastapi import Request
from openai import AsyncOpenAI

_upstream_client: Optional[AsyncOpenAI] = None


def get_upstream_client(provider: str = "baseten") -> AsyncOpenAI:
    """Return the appropriate client based on provider and available keys."""
    global _upstream_client
    if _upstream_client is not None:
        return _upstream_client

    meta_key = os.getenv("META_API_KEY")
    baseten_key = os.getenv("BASETEN_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if provider == "meta" and meta_key:
        base_url = os.getenv("META_BASE_URL", "https://api.meta.ai/v1")
        return AsyncOpenAI(api_key=meta_key, base_url=base_url)
    elif baseten_key:
        base_url = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")
        return AsyncOpenAI(api_key=baseten_key, base_url=base_url)
    elif openai_key:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return AsyncOpenAI(api_key=openai_key, base_url=base_url)
    else:
        # Fallback dummy for offline testing
        return AsyncOpenAI(api_key="sk-dummy-key", base_url=None)


def set_upstream_client(client: Optional[AsyncOpenAI]) -> None:
    global _upstream_client
    _upstream_client = client


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
            lower_content = content.lower()
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

    return (
        f"> ⚡ **Ysolveth Triage**: `{tier}` → `{target_model}` ({triage_str})\n"
        f"> 🔍 **PolyFabric AST**: {pruned_str}\n"
        f"> 🧠 **Veylqora Memory**: `ACTIVE` ({stale_str})\n\n"
    )


async def stream_chat_completion(
    payload: dict,
    request: Optional[Request] = None,
    target_model: Optional[str] = None,
    client: Optional[AsyncOpenAI] = None,
    is_auxiliary: Optional[bool] = None,
    telemetry_header: Optional[str] = None,
) -> AsyncGenerator[str, None]:
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

    emitted_telemetry = False

    # 1. Emit telemetry chunk only for primary user coding requests
    if not is_auxiliary:
        if telemetry_header is None:
            telemetry_header = get_default_telemetry_banner(target_model=target_model)

        if telemetry_header:
            first_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": target_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": telemetry_header},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(first_chunk)}\n\n"
            emitted_telemetry = True

    # 2. Open upstream stream
    create_kwargs: Dict[str, Any] = {
        "model": target_model,
        "messages": payload.get("messages", []),
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": payload.get("temperature", 0.2),
        "max_tokens": payload.get("max_tokens", 4096),
    }
    for key in ["tools", "tool_choice", "response_format", "stop", "top_p", "presence_penalty", "frequency_penalty"]:
        if key in payload and payload[key] is not None:
            create_kwargs[key] = payload[key]

    upstream = None
    is_first_upstream_chunk = True
    try:
        upstream = await client.chat.completions.create(**create_kwargs)

        async for chunk in upstream:
            # Check client disconnect
            if request is not None and await request.is_disconnected():
                break

            if hasattr(chunk, "model_dump"):
                chunk_dict = chunk.model_dump(exclude_none=True)
            elif isinstance(chunk, dict):
                chunk_dict = dict(chunk)
            else:
                chunk_dict = json.loads(str(chunk))

            # Maintain stable request ID across stream
            chunk_dict["id"] = req_id

            # Normalize choices and enforce role invariant
            skip_chunk = False
            if "choices" in chunk_dict and chunk_dict["choices"]:
                for choice in chunk_dict["choices"]:
                    delta = choice.get("delta")
                    if isinstance(delta, dict):
                        if "role" in delta:
                            if emitted_telemetry:
                                # Strip duplicate role if telemetry banner was already emitted
                                delta.pop("role", None)
                            elif isinstance(delta["role"], str):
                                # Ensure strictly no leading or trailing spaces
                                delta["role"] = delta["role"].strip()
                        elif is_first_upstream_chunk and not emitted_telemetry:
                            # Ensure first chunk role invariant
                            delta["role"] = "assistant"

                # If popping duplicate role left delta completely empty without finish_reason, skip no-op chunk
                choice_0 = chunk_dict["choices"][0]
                delta_0 = choice_0.get("delta", {})
                if not delta_0 and choice_0.get("finish_reason") is None and not chunk_dict.get("usage"):
                    skip_chunk = True

            is_first_upstream_chunk = False
            if not skip_chunk:
                yield f"data: {json.dumps(chunk_dict)}\n\n"

    except Exception as e:
        error_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": target_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": f"\n\n> ❌ **Musegix Gateway Error**: {type(e).__name__} - {str(e)}"
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

    finally:
        if upstream is not None and hasattr(upstream, "close"):
            try:
                res = upstream.close()
                if inspect.isawaitable(res):
                    await res
            except Exception:
                pass

    yield "data: [DONE]\n\n"
