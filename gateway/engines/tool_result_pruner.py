"""PolyFabric tool-result pruning: shrink OLD, successful tool outputs in agent history.

Bolt's agent loop resends the full conversation on every step, including every
project_read_file / project_run_command result. Early results become stale as
the agent edits, but they still cost tokens on every later request.

Rules (deliberately conservative, so the repair loop keeps its evidence):
- The most recent `keep_last` tool results are never touched.
- Results that report a failure (isError, problems, non-zero exitCode, errors) are never touched.
- Only results longer than `min_chars` are candidates.
- A pruned result keeps its first 160 characters and a marker stating what was removed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from gateway.engines.polyfabric_pruner import count_tokens

_FAILURE = re.compile(
    r'"isError"\s*:\s*true|"problems"\s*:|"exitCode"\s*:\s*[1-9]|"error"\s*:|Patch conflict|Syntax check failed|TSC_EXIT:[1-9]',
    re.IGNORECASE,
)


def is_failed_tool_result(text: str) -> bool:
    """True when a tool result reports a failure (these results are never pruned)."""
    return bool(_FAILURE.search(text or ""))


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def prune_tool_results(
    messages: List[Dict[str, Any]],
    keep_last: int = 6,
    min_chars: int = 400,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Return (messages, tokens_before, tokens_after). Input list is not mutated."""
    tool_idx = [i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "tool"]
    candidates = tool_idx[:-keep_last] if keep_last > 0 else tool_idx

    out = [dict(m) if isinstance(m, dict) else m for m in messages]
    before = after = 0
    for i in candidates:
        text = _text(out[i].get("content"))
        if len(text) < min_chars or _FAILURE.search(text):
            continue
        tokens = count_tokens(text)
        stub = (
            text[:160]
            + f"\n...[PolyFabric: old tool output pruned, {len(text)} chars / {tokens} tokens. "
            "Re-read the file if you need its exact contents.]"
        )
        before += tokens
        after += count_tokens(stub)
        out[i]["content"] = stub
    return out, before, after
