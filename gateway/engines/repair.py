"""Repair-loop helpers for the gateway: which file to keep whole, what a change breaks, and tier escalation.

Nothing here is wired into a request on its own except repair_target_file (used by routes.py to
keep the failing file whole) and referenced_mutations (used by the Veylqora banner).
escalate_after_failures is a helper only and is not called yet.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from gateway.engines.tool_result_pruner import is_failed_tool_result

TIER_ORDER = ["TRIVIAL", "MODERATE", "HARD"]
ESCALATE_AFTER = 2

_FILE_LINE = re.compile(
    r"(/?(?:[\w@.\-]+[\\/])*[\w@.\-]+\.(?:tsx?|jsx?|mjs|cjs|py|css|html|json|vue|svelte)):(\d+)"
)


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def tool_failure_flags(messages: Iterable[Dict[str, Any]]) -> List[bool]:
    """One flag per tool result, oldest first: True when that result reports a failure."""
    return [
        is_failed_tool_result(_text(m.get("content")))
        for m in messages
        if isinstance(m, dict) and m.get("role") == "tool"
    ]


def repair_target_file(messages: Sequence[Dict[str, Any]]) -> Optional[str]:
    """File named as file:line by the newest tool result, when that result is a failure.

    Returns None when the newest tool result is a success, names no file:line, or there is none.
    The path is normalised to be relative to the project (a /home/project/ prefix is removed).
    """
    newest = None
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "tool":
            newest = m
    if newest is None:
        return None
    text = _text(newest.get("content"))
    if not is_failed_tool_result(text):
        return None
    m = _FILE_LINE.search(text)
    if not m:
        return None
    path = m.group(1).replace("\\", "/")
    if path.startswith("/home/project/"):
        path = path[len("/home/project/"):]
    return path.lstrip("/")


def referenced_mutations(mutated: Iterable[Any], files: Dict[str, str]) -> Dict[str, List[str]]:
    """Changed symbols (from VeylqoraGuard's report) that other files in the turn refer to.

    `mutated` items need file_path and symbol_name (MutatedSymbol or any duck-typed object).
    `files` maps path -> current content. Returns {symbol: [referencing paths]} with only non-empty entries.
    """
    result: Dict[str, List[str]] = {}
    for sym in mutated:
        name = getattr(sym, "symbol_name", "")
        origin = getattr(sym, "file_path", "")
        if not name or name == "$file":
            continue
        base = name.split(".")[-1]
        pattern = re.compile(r"\b" + re.escape(base) + r"\b")
        users = [p for p, body in files.items() if p != origin and pattern.search(body or "")]
        if users:
            bucket = result.setdefault(name, [])
            for u in users:
                if u not in bucket:
                    bucket.append(u)
    return result


def impact_banner(impact: Dict[str, List[str]], limit: int = 5) -> Optional[str]:
    if not impact:
        return None
    parts = [f"`{sym}` used by {', '.join(f'`{p}`' for p in paths[:3])}" for sym, paths in list(impact.items())[:limit]]
    return "> 🧠 **Veylqora impact**: changed exports still referenced: " + "; ".join(parts) + "\n"


def escalate_after_failures(tier: str, failures: Sequence[bool]) -> str:
    """Return the next stronger tier after ESCALATE_AFTER or more consecutive failed tool results.

    `failures` is ordered oldest to newest (True = failed). Unknown tiers are returned unchanged.
    """
    if tier not in TIER_ORDER:
        return tier
    streak = 0
    for failed in reversed(list(failures)):
        if not failed:
            break
        streak += 1
    if streak < ESCALATE_AFTER:
        return tier
    idx = TIER_ORDER.index(tier)
    return TIER_ORDER[min(idx + 1, len(TIER_ORDER) - 1)]
