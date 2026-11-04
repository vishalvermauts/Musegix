import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

# Ensure .env is loaded
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from gateway.engines.ysolveth_classifier import YsolvethClassifier
from gateway.engines.polyfabric_pruner import PolyFabricPruner, count_tokens
from gateway.engines.veylqora_guard import VeylqoraGuard
from gateway.prompt_extract import latest_user_prompt
from gateway.tool_choice import (
    MAX_ENFORCEMENT_ATTEMPTS,
    apply_tool_choice_policy,
    kwargs_for_attempt,
    recover_tool_calls,
    strip_private,
)
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


def _chat_session_id(messages) -> str:
    """bolt.diy sends no chat id; the first user message is stable within one chat."""
    import hashlib
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, list):
                c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            if isinstance(c, str) and c.strip():
                return "chat_" + hashlib.sha256(c.strip()[:500].encode("utf-8")).hexdigest()[:16]
    return "bolt-session-default"


def get_guard() -> VeylqoraGuard:
    global _guard
    if _guard is None:
        _guard = VeylqoraGuard()
    return _guard


_DUMP_DIR = Path(__file__).resolve().parent.parent / "data" / "requests"
_PRUNE_REPORTED: dict = {}


def _debug_dump(body: dict, classified_text: str) -> None:
    """Set MUSEGIX_DUMP_REQUESTS=1 to save every incoming request (secrets never appear in bodies)."""
    if os.getenv("MUSEGIX_DUMP_REQUESTS") != "1":
        return
    _DUMP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time() * 1000)}.json"
    roles = [m.get("role") for m in body.get("messages", []) if isinstance(m, dict)]
    (_DUMP_DIR / name).write_text(json.dumps(body, indent=1, ensure_ascii=False), encoding="utf-8")
    logger.info(
        f"[dump] {name} roles={roles} tools={len(body.get('tools') or [])} "
        f"classified_text({len(classified_text)} chars)={classified_text[:300]!r}"
    )


def _tool_call_fallback(provider: str):
    """Escalation target when the routed model keeps skipping a required tool call.

    The Baseten open-weights tier is cheapest but less reliable on long agent contexts;
    Muse Spark 1.3 on Meta passed 10/10 forced-tool probes, so it is the fallback.
    """
    if provider == "baseten" and os.getenv("META_API_KEY"):
        return (get_upstream_client(provider="meta"), "muse-spark-1.3", "meta")
    return None


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
    # bolt.diy wraps typed prompts in "[Model: ...]\n\n[Provider: ...]\n\n"; that wrapper
    # flipped Ysolveth's tier on 5/20 prompts (scripts/ysolveth_wrapper_check.py), so strip it.
    user_prompt = latest_user_prompt(messages)

    _debug_dump(body, user_prompt)

    is_aux = is_auxiliary_request(body)
    model_param = body.get("model")

    tier = "MODERATE"
    target_model = "muse-spark-1.3"
    provider = "meta"
    triage_ms = None

    # 2. Ysolveth System One Triage (only for the user's coding prompt; bolt.diy's summary /
    #    context-selection / enhancer calls carry templates, not a task, so they keep the default)
    if is_aux and (not model_param or model_param == "musecontext-auto"):
        pass
    elif not model_param or model_param == "musecontext-auto":
        try:
            clf = get_classifier()
            triage_res = clf.classify(user_prompt or "code generation")
            tier = triage_res["tier"]
            target_model = triage_res["target_model"]
            provider = triage_res["provider"]
            triage_ms = triage_res["latency_ms"]

            # Multi-file or full application requests require advanced reasoning (Meta Muse Spark/Wonder)
            # over the open-weight lightweight tier
            lower_prompt = user_prompt.lower()
            scaffold_keywords = ["portfolio", "website", "fullstack", "dashboard", "showcase", "application", "multi-file"]
            if tier == "TRIVIAL" and any(k in lower_prompt for k in scaffold_keywords):
                tier = "MODERATE"
                target_model = "muse-spark-1.3"
                provider = "meta"
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
        # Veylqora must fingerprint the ORIGINAL files, not PolyFabric's pruned stubs,
        # otherwise every pruned background file looks "mutated".
        original_files = {}
        for m in messages:
            if isinstance(m, dict) and m.get("role") != "system" and isinstance(m.get("content"), str):
                for match in re.finditer(r'<boltAction\s+type="file"\s+filePath="([^"]+)">\s*(.*?)\s*</boltAction>', m["content"], re.DOTALL):
                    original_files[match.group(1)] = match.group(2)

        # Check if there is bolt multi-file context to prune
        for msg in messages:
            # System prompts hold bolt.diy's <boltAction> *examples*; never rewrite instructions.
            if isinstance(msg, dict) and msg.get("role") != "system" and isinstance(msg.get("content"), str):
                content = msg["content"]
                if "<boltArtifact" in content or '<boltAction type="file"' in content:
                    try:
                        pruner_engine = get_pruner()
                        prune_res = pruner_engine.prune_context(
                            context_text=content,
                            user_prompt=user_prompt
                        )
                        selected_tokens = (selected_tokens or 0) + prune_res.pruned_tokens
                        raw_tokens = (raw_tokens or 0) + prune_res.raw_tokens
                        logger.info(
                            f"[polyfabric] {prune_res.raw_tokens} -> {prune_res.pruned_tokens} tokens "
                            f"kept={prune_res.preserved_files} pruned={len(prune_res.pruned_files)} files "
                            f"({prune_res.elapsed_ms}ms)"
                        )
                        msg["content"] = prune_res.pruned_text
                    except Exception as e:
                        logger.warning(f"PolyFabric pruning exception: {e}")

        # Veylqora session check
        try:
            guard_engine = get_guard()
            session_id = body.get("session_id") or _chat_session_id(messages)
            extracted_files = original_files
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
    extra_banner = None
    if not is_aux:
        telemetry_header = get_default_telemetry_banner(
            tier=tier,
            target_model=target_model,
            triage_ms=triage_ms,
            selected_tokens=selected_tokens,
            raw_tokens=raw_tokens,
            stale_memories=stale_memories,
        )
        # bolt.diy attaches the project snapshot only from the 2nd agent step on, after the
        # first-step banner has gone out. Report the first real pruning of each prompt once.
        if raw_tokens and selected_tokens is not None and raw_tokens > selected_tokens:
            turn_key = f"{body.get('session_id', '')}|{len(messages and [m for m in messages if m.get('role') == 'user'])}|{user_prompt}"
            if turn_key not in _PRUNE_REPORTED:
                _PRUNE_REPORTED[turn_key] = True
                if len(_PRUNE_REPORTED) > 500:
                    _PRUNE_REPORTED.pop(next(iter(_PRUNE_REPORTED)))
                pct = (raw_tokens - selected_tokens) / raw_tokens * 100
                extra_banner = (
                    f"> 🔍 **PolyFabric AST**: `{selected_tokens}` tokens vs `{raw_tokens}` raw "
                    f"({pct:.1f}% pruned)\n\n"
                )

    client = get_upstream_client(provider=provider)
    # OpenAI spec: an absent "stream" means a non-streaming JSON response. bolt.diy's
    # generateText calls (chat summary, context selection) omit it and fail on SSE.
    stream = bool(body.get("stream", False))

    if stream:
        return StreamingResponse(
            stream_chat_completion(
                payload=body,
                request=request,
                target_model=target_model,
                client=client,
                is_auxiliary=is_aux,
                telemetry_header=telemetry_header,
                provider=provider,
                fallback=_tool_call_fallback(provider),
                extra_banner=extra_banner,
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

        # Meta API only supports tool_choice="auto"; emulate required/named choices (gateway/tool_choice.py)
        enforcement = apply_tool_choice_policy(create_kwargs, provider)

        try:
            attempts = MAX_ENFORCEMENT_ATTEMPTS if enforcement else 1
            for attempt in range(attempts):
                kw = kwargs_for_attempt(create_kwargs, enforcement, attempt) if enforcement else strip_private(create_kwargs)
                resp = await client.chat.completions.create(**kw)
                if hasattr(resp, "model_dump"):
                    resp_dict = resp.model_dump()
                elif isinstance(resp, dict):
                    resp_dict = dict(resp)
                else:
                    resp_dict = json.loads(str(resp))
                if enforcement is None or not resp_dict.get("choices"):
                    break
                choice0 = resp_dict["choices"][0]
                msg0 = choice0.get("message") or {}
                names = [((tc or {}).get("function") or {}).get("name") for tc in msg0.get("tool_calls") or []]
                if any(enforcement.satisfied_by(n) for n in names):
                    break
                recovered = recover_tool_calls(msg0.get("content") or "", kw.get("tools"), enforcement)
                if recovered:
                    msg0["tool_calls"] = recovered
                    msg0["content"] = None
                    choice0["finish_reason"] = "tool_calls"
                    break
                logger.warning(f"Non-streaming: no required tool call (attempt {attempt + 1}/{attempts})")

            # Ensure choices and message content invariants for Vercel AI SDK
            if "choices" in resp_dict and resp_dict["choices"]:
                for choice in resp_dict["choices"]:
                    msg = choice.get("message")
                    if isinstance(msg, dict):
                        if msg.get("content") is None and not msg.get("tool_calls"):
                            # If model only returned reasoning or empty content, extract reasoning or default
                            msg["content"] = msg.get("reasoning_content") or "Ready"
            return JSONResponse(resp_dict)
        except Exception as e:
            logger.error(f"Upstream provider error in non-streaming chat: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Upstream provider error: {type(e).__name__} - {str(e)}",
            )
