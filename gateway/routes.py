import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from gateway.streaming import stream_chat_completion

router = APIRouter(prefix="/v1")

@router.get("/models")
async def list_models():
    return JSONResponse({
        "object": "list",
        "data": [
            {
                "id": "musecontext-auto",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "musegix-system",
            }
        ]
    })

@router.post("/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Missing 'messages' in request body")

    stream = body.get("stream", True)
    if stream:
        return StreamingResponse(
            stream_chat_completion(body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Non-streaming mock for API compliance
        return JSONResponse({
            "id": f"chatcmpl-{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "musecontext-auto",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Musegix gateway ready."
                    },
                    "finish_reason": "stop"
                }
            ]
        })
