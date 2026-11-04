import json
import logging
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

# Ensure .env is loaded
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from gateway.engines.ysolveth_classifier import YsolvethClassifier
from gateway.engines.polyfabric_pruner import PolyFabricPruner, count_tokens
from gateway.engines.veylqora_guard import VeylqoraGuard
from gateway.streaming import (
    stream_chat_completion,
    get_upstream_client,
    is_auxiliary_request,
    get_default_telemetry_banner,
)

logger = logging.getLogger("gateway.routes")
router = APIRouter(prefix="/v1")

# Initialize engines
_classifier: Optional[YsolvethClassifier] = None
_pruner: Optional[PolyFabricPruner] = None
_guard: Optional[VeylqoraGuard] = None


def get_classifier() -> YsolvethClassifier:
    global _classifier
    if _classifier is None:
        _classifier = YsolvethClassifier()
    return _classifier


def get_pruner() -> PolyFabricPruner:
    global _pruner
    if _pruner is None:
        _pruner = PolyFabricPruner()
    return _pruner


def get_guard() -> VeylqoraGuard:
    global _guard
    if _guard is None:
        _guard = VeylqoraGuard()
    return _guard


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

    # 1. Extract latest user prompt
    user_prompt = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            c = msg.get("content", "")
            if isinstance(c, list):
                user_prompt = " ".join(
                    p.get("text", "") for p in c if isinstance(p, dict) and "text" in p
                )
            elif isinstance(c, str):
                user_prompt = c
            break

    is_aux = is_auxiliary_request(body)
    model_param = body.get("model")

    tier = "MODERATE"
    target_model = "muse-spark-1.3"
    provider = "meta"
    triage_ms = None

    # 2. Ysolveth System One Triage
    if not model_param or model_param == "musecontext-auto":
        try:
            clf = get_classifier()
            triage_res = clf.classify(user_prompt or "code generation")
            tier = triage_res["tier"]
            target_model = triage_res["target_model"]
            provider = triage_res["provider"]
            triage_ms = triage_res["latency_ms"]
        except Exception as e:
            logger.warning(f"Ysolveth triage fallback: {e}")
            tier = "MODERATE"
            target_model = "muse-spark-1.3"
            provider = "meta"
    elif "muse-spark-open" in model_param or "open-1026" in model_param:
        target_model = "meta-models/muse-spark-open-1026"
        provider = "baseten"
        tier = "TRIVIAL"
    elif "wonder" in model_param:
        target_model = "muse-wonder-1.0"
        provider = "meta"
        tier = "HARD"
    elif "spark" in model_param:
        target_model = "muse-spark-1.3"
        provider = "meta"
        tier = "MODERATE"
    else:
        target_model = model_param
        provider = "meta" if os.getenv("META_API_KEY") else "baseten"

    # 3. PolyFabric AST Context Pruning & Veylqora Memory Inspection
    selected_tokens = None
    raw_tokens = None
    stale_memories = None

    if not is_aux:
        # Check if there is bolt multi-file context to prune
        for msg in messages:
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                content = msg["content"]
                if "<boltArtifact" in content or '<boltAction type="file"' in content:
                    try:
                        pruner_engine = get_pruner()
                        prune_res = pruner_engine.prune_context(
                            context_text=content,
                            user_prompt=user_prompt
                        )
                        selected_tokens = prune_res.pruned_tokens
                        raw_tokens = prune_res.raw_tokens
                        msg["content"] = prune_res.pruned_text
                    except Exception as e:
                        logger.warning(f"PolyFabric pruning exception: {e}")

        # Veylqora session check
        try:
            guard_engine = get_guard()
            session_id = body.get("session_id", "bolt-session-default")
            # Extract file dictionary if available in prompt
            extracted_files = {}
            for m in messages:
                if isinstance(m, dict) and isinstance(m.get("content"), str):
                    for match in re.finditer(r'<boltAction\s+type="file"\s+filePath="([^"]+)">\s*(.*?)\s*</boltAction>', m["content"], re.DOTALL):
                        extracted_files[match.group(1)] = match.group(2)
            if extracted_files:
                rep = guard_engine.inspect_turn(session_id, extracted_files, advance_turn=True)
                stale_memories = rep.stale_count if hasattr(rep, 'stale_count') else len(rep.mutated_symbols)
            else:
                stale_memories = 0
        except Exception as e:
            logger.warning(f"Veylqora check exception: {e}")
            stale_memories = 0

    # 4. Telemetry Header Construction
    telemetry_header = None
    if not is_aux:
        telemetry_header = get_default_telemetry_banner(
            tier=tier,
            target_model=target_model,
            triage_ms=triage_ms,
            selected_tokens=selected_tokens,
            raw_tokens=raw_tokens,
            stale_memories=stale_memories,
        )

    client = get_upstream_client(provider=provider)
    stream = body.get("stream", True)

    if stream:
        return StreamingResponse(
            stream_chat_completion(
                payload=body,
                request=request,
                target_model=target_model,
                client=client,
                is_auxiliary=is_aux,
                telemetry_header=telemetry_header,
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
        max_tokens_val = body.get("max_tokens", 4096)
        if max_tokens_val and max_tokens_val < 512:
            max_tokens_val = 1024

        create_kwargs = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "temperature": body.get("temperature", 0.2),
            "max_tokens": max_tokens_val,
        }
        for key in ["tools", "tool_choice", "response_format", "stop", "top_p", "presence_penalty", "frequency_penalty"]:
            if key in body and body[key] is not None:
                create_kwargs[key] = body[key]

        try:
            resp = await client.chat.completions.create(**create_kwargs)
            if hasattr(resp, "model_dump"):
                resp_dict = resp.model_dump()
            elif isinstance(resp, dict):
                resp_dict = dict(resp)
            else:
                resp_dict = json.loads(str(resp))

            # Ensure choices and message content invariants for Vercel AI SDK
            if "choices" in resp_dict and resp_dict["choices"]:
                for choice in resp_dict["choices"]:
                    msg = choice.get("message")
                    if isinstance(msg, dict):
                        if msg.get("content") is None:
                            # If model only returned reasoning or empty content, extract reasoning or default
                            msg["content"] = msg.get("reasoning_content") or "Ready"
            return JSONResponse(resp_dict)
        except Exception as e:
            logger.error(f"Upstream provider error in non-streaming chat: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Upstream provider error: {type(e).__name__} - {str(e)}",
            )
