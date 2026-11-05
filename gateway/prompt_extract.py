"""Recover the text the user actually typed from a bolt.diy request.

bolt.diy prepends "[Model: <id>]\\n\\n[Provider: <name>]\\n\\n" to every user message
(app/utils/constants.ts MODEL_REGEX / PROVIDER_REGEX) and may send content as a list of
parts (text + images). Ysolveth was trained on bare prompts, so the wrapper is removed
before classification.
"""

import re
from typing import Any, Dict, List

_MODEL_RE = re.compile(r"^\s*\[Model: [^\]\n]*\]\s*", re.IGNORECASE)
_BOLT_ARTIFACT_RE = re.compile(r"<boltArtifact\b[\s\S]*?</boltArtifact>", re.IGNORECASE)
_PROVIDER_RE = re.compile(r"^\s*\[Provider: [^\]\n]*\]\s*", re.IGNORECASE)


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type", "text") == "text"
        )
    return ""


def clean_user_prompt(text: str) -> str:
    """Strip bolt.diy's [Model: ...] / [Provider: ...] header lines."""
    prev = None
    while prev != text:
        prev = text
        text = _PROVIDER_RE.sub("", _MODEL_RE.sub("", text))
    return text.strip()


def latest_user_prompt(messages: List[Dict[str, Any]]) -> str:
    """Cleaned text of the most recent message the user typed.

    Messages typed in bolt.diy's chat box carry the [Model: ...] header; synthetic user
    messages bolt injects (template setup, continuations) do not, so a header'd message wins.
    Falls back to the latest non-empty user message.
    """
    fallback = ""
    for msg in reversed(messages or []):
        if not (isinstance(msg, dict) and msg.get("role") == "user"):
            continue
        raw = _text_of(msg.get("content"))
        # bolt.diy appends the typed request AFTER its "User Updated Files" code snapshot
        # (<boltArtifact> block) in the same user message: keep only the typed part.
        cleaned = clean_user_prompt(_BOLT_ARTIFACT_RE.sub("", raw)).strip()
        if not cleaned:
            continue
        if _MODEL_RE.match(raw):
            return cleaned
        fallback = fallback or cleaned
    return fallback
