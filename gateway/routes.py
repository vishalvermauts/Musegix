import json
import os
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from gateway.streaming import (
    stream_chat_completion,
    get_upstream_client,
    is_auxiliary_request,
)

router = APIRouter(prefix="/v1")


@router.get("/models")
async def list_models():
    now = int(time.time())
    return JSONResponse({
        "object": "list",
        "data": [
            {
                "id": "musecontext-auto",
                "object": "model",
                "created": now,
                "owned_by": "musegix-system",
            },
            {
                "id": "muse-spark-1.3",
                "object": "model",
                "created": now,
                "owned_by": "musegix-system",
            },
            {
                "id": "muse-spark-open",
                "object": "model",
                "created": now,
                "owned_by": "musegix-system",
            },
            {
                "id": "muse-wonder-1.0",
                "object": "model",
                "created": now,
                "owned_by": "musegix-system",
            },
        ],
    })


@router.post("/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    messages = body.get("messages", [])
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="Missing 'messages' in request body")

    model_param = body.get("model")
    if not model_param or model_param == "musecontext-auto":
        target_model = os.getenv("DEFAULT_MODEL", "muse-spark-1.3")
    else:
        target_model = model_param

    client = get_upstream_client()
    stream = body.get("stream", True)
    is_aux = is_auxiliary_request(body)

    if stream:
        return StreamingResponse(
            stream_chat_completion(
                payload=body,
                request=request,
                target_model=target_model,
                client=client,
                is_auxiliary=is_aux,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Full non-streaming passthrough to upstream client
        create_kwargs = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "temperature": body.get("temperature", 0.2),
            "max_tokens": body.get("max_tokens", 4096),
        }
        for key in ["tools", "tool_choice", "response_format", "stop", "top_p", "presence_penalty", "frequency_penalty"]:
            if key in body and body[key] is not None:
                create_kwargs[key] = body[key]

        try:
            resp = await client.chat.completions.create(**create_kwargs)
            if hasattr(resp, "model_dump"):
                resp_dict = resp.model_dump(exclude_none=True)
            elif isinstance(resp, dict):
                resp_dict = resp
            else:
                resp_dict = json.loads(str(resp))
            return JSONResponse(resp_dict)
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Upstream provider error: {type(e).__name__} - {str(e)}",
            )
