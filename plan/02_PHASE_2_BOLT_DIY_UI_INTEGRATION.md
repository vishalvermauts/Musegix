# Phase 2: Upstream Generation Proxy & Full `bolt.diy` UI Integration

> **Status:** Active Execution  
> **Objective:** Upgrade the gateway from an echo stub to a robust, bidirectional OpenAI-compatible proxy that calls upstream models (Meta / Baseten / OpenAI), cleanly passes through auxiliary `bolt.diy` requests (prompt enhancement, summaries), and verifies full file streaming into WebContainer.

---

## 1. Upstream Proxy & Streaming Architecture (`gateway/streaming.py`)

### Requirements
1. **Real Model Generation:** Call upstream model using `AsyncOpenAI`.
2. **Auxiliary Request Passthrough:**
   - Detect prompt enhancement calls and context-selection calls.
   - Do NOT inject telemetry banners into auxiliary calls.
3. **Usage Token Capture:** Request `stream_options={"include_usage": True}` to capture true input and output token counts directly from the upstream provider.
4. **SSE Normalization:**
   - Single consistent request ID `chatcmpl-mgx-{timestamp}` across all chunks.
   - Ensure `choices[0].delta.role == "assistant"` with zero whitespace.
   - Forward `tool_calls` deltas without modification.
5. **Connection Lifecycle:** Check `await request.is_disconnected()` in the streaming loop and close upstream streams on client disconnect.

### Core Implementation
```python
import json
import time
from typing import AsyncGenerator
from fastapi import Request
from openai import AsyncOpenAI

async def stream_chat_completion(
    payload: dict,
    request: Request,
    target_model: str,
    client: AsyncOpenAI,
    is_auxiliary: bool = False,
    telemetry_header: str = ""
) -> AsyncGenerator[str, None]:
    t0 = time.perf_counter()
    req_id = f"chatcmpl-mgx-{int(time.time() * 1000)}"
    
    # 1. Emit Telemetry Chunk only for primary user coding requests
    if not is_auxiliary and telemetry_header:
        first_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": target_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": telemetry_header},
                    "finish_reason": None
                }
            ]
        }
        yield f"data: {json.dumps(first_chunk)}\n\n"

    # 2. Open upstream stream
    try:
        upstream = await client.chat.completions.create(
            model=target_model,
            messages=payload.get("messages", []),
            stream=True,
            stream_options={"include_usage": True},
            temperature=payload.get("temperature", 0.2),
            max_tokens=payload.get("max_tokens", 4096),
            tools=payload.get("tools"),
            tool_choice=payload.get("tool_choice")
        )
        
        async for chunk in upstream:
            # Check client disconnect
            if await request.is_disconnected():
                break
                
            chunk_dict = chunk.model_dump(exclude_none=True)
            chunk_dict["id"] = req_id
            
            # Normalize choices
            if "choices" in chunk_dict and chunk_dict["choices"]:
                choice = chunk_dict["choices"][0]
                # Strip duplicate role if telemetry banner was already emitted
                if not is_auxiliary and telemetry_header and "delta" in choice:
                    choice["delta"].pop("role", None)
                    
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
                    "delta": {"content": f"\n\n> ❌ **Musegix Gateway Error**: {type(e).__name__} - {str(e)}"},
                    "finish_reason": "stop"
                }
            ]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

    yield "data: [DONE]\n\n"
```

---

## 2. Non-Streaming Passthrough (`gateway/routes.py`)

Non-streaming calls (used by `bolt.diy` context selection and title generators) must NOT return static strings. They must call upstream directly:
```python
@router.post("/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    stream = body.get("stream", True)
    
    if not stream:
        # Full non-streaming passthrough
        resp = await client.chat.completions.create(
            model=target_model,
            messages=body.get("messages", []),
            temperature=body.get("temperature", 0.2),
            max_tokens=body.get("max_tokens", 4096)
        )
        return JSONResponse(resp.model_dump())
```

---

## 3. Phase 2 Certification Gate Checklist

- [ ] **Gate 2.1:** Upstream client configured with genuine base URLs and API keys.
- [ ] **Gate 2.2:** Non-streaming endpoint returns genuine model response (zero mock strings).
- [ ] **Gate 2.3:** Auxiliary calls (enhancer, title generator) pass through cleanly without telemetry injection.
- [ ] **Gate 2.4:** `bolt.diy` WebContainer successfully generates a complete multi-file application (e.g. Counter or Todo App) through the gateway.
- [ ] **Gate 2.5:** Upstream tool calls (`tools` & `tool_choice`) survive round-trip without argument loss.
- [ ] **Gate 2.6:** Client cancellation (clicking Stop in `bolt.diy`) terminates upstream stream within 100ms.
