"""
Tool-choice emulation for upstreams that only accept ``tool_choice="auto"``.

Meta Model API rejects ``"required"``, ``"none"`` and named function choices with HTTP 400
(verified 2026-11-04 against muse-spark-1.3). bolt.diy's agent loop depends on them:
it forces ``agent_plan`` on the first step and ``"required"`` on edit steps, and the
AI SDK throws ``ToolChoiceViolationError`` if the step contains no matching tool call.

The gateway therefore:
  * sends ``"auto"`` upstream,
  * narrows ``tools`` to the named function when a specific tool is forced,
  * adds a system instruction requiring a tool call,
  * checks the upstream result and retries (or recovers JSON tool calls printed as text)
    before anything reaches bolt.diy.
"""

import copy
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

MAX_ENFORCEMENT_ATTEMPTS = 3  # initial call + 2 retries


@dataclass
class ToolEnforcement:
    kind: str  # "required" | "tool"
    tool_name: Optional[str] = None

    def satisfied_by(self, name: Optional[str]) -> bool:
        if not name:
            return False
        return self.kind == "required" or name == self.tool_name


def _tool_names(tools: Optional[List[Dict[str, Any]]]) -> List[str]:
    names = []
    for t in tools or []:
        fn = t.get("function") if isinstance(t, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            names.append(fn["name"])
    return names


def _instruction(enf: ToolEnforcement, attempt: int) -> str:
    target = f"the `{enf.tool_name}` tool" if enf.kind == "tool" else "one of the provided tools"
    msg = (
        f"MANDATORY: Your reply MUST be a native function/tool call to {target}. "
        "Do not answer with prose only, do not print JSON or code instead of calling the tool."
    )
    if attempt > 0:
        msg += " Your previous reply did not call the tool. Call it now."
    return msg


def _add_system_instruction(messages: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
    msgs = copy.deepcopy(messages)
    if msgs and msgs[0].get("role") == "system" and isinstance(msgs[0].get("content"), str):
        msgs[0]["content"] = f"{msgs[0]['content']}\n\n{text}"
    else:
        msgs.insert(0, {"role": "system", "content": text})
    return msgs


# Providers verified (2026-11-04) to accept "required" and named tool_choice natively.
NATIVE_TOOL_CHOICE_PROVIDERS = {"baseten", "openai"}


def enforcement_for(tool_choice: Any, tools: Optional[List[Dict[str, Any]]]) -> Optional[ToolEnforcement]:
    if not tools or tool_choice in (None, "auto", "none"):
        return None
    if tool_choice == "required":
        return ToolEnforcement("required")
    if isinstance(tool_choice, dict):
        name = (tool_choice.get("function") or {}).get("name") or tool_choice.get("name")
        if name and name in _tool_names(tools):
            return ToolEnforcement("tool", name)
        return ToolEnforcement("required")
    return None


def apply_tool_choice_policy(create_kwargs: Dict[str, Any], provider: str = "meta") -> Optional[ToolEnforcement]:
    """Rewrite ``create_kwargs`` in place for the target provider.

    Providers in NATIVE_TOOL_CHOICE_PROVIDERS get tool_choice unchanged (the gateway still
    verifies the result). Others (Meta) only see ``tool_choice="auto"`` and the choice is emulated.
    Returns the enforcement the gateway must check on the response, or None.
    """
    if "tool_choice" not in create_kwargs:
        return None

    tc = create_kwargs["tool_choice"]
    if tc == "auto":
        return None
    if (provider or "").lower() in NATIVE_TOOL_CHOICE_PROVIDERS:
        enf = enforcement_for(tc, create_kwargs.get("tools"))
        if enf is not None:
            create_kwargs["_base_messages"] = create_kwargs["messages"]
        return enf
    if tc == "none":
        create_kwargs.pop("tools", None)
        create_kwargs.pop("tool_choice", None)
        return None

    create_kwargs["tool_choice"] = "auto"
    if not create_kwargs.get("tools"):
        create_kwargs.pop("tool_choice", None)
        return None

    enf: Optional[ToolEnforcement] = None
    if tc == "required":
        enf = ToolEnforcement("required")
    elif isinstance(tc, dict):
        name = (tc.get("function") or {}).get("name") or tc.get("name")
        if name and name in _tool_names(create_kwargs["tools"]):
            # Only expose the forced tool so "auto" cannot pick a different one.
            create_kwargs["tools"] = [
                t for t in create_kwargs["tools"] if (t.get("function") or {}).get("name") == name
            ]
            enf = ToolEnforcement("tool", name)
        else:
            enf = ToolEnforcement("required")

    if enf is not None:
        create_kwargs["_base_messages"] = create_kwargs["messages"]
        create_kwargs["messages"] = _add_system_instruction(create_kwargs["messages"], _instruction(enf, 0))
    return enf


def kwargs_for_attempt(create_kwargs: Dict[str, Any], enf: ToolEnforcement, attempt: int) -> Dict[str, Any]:
    """Upstream kwargs for a given attempt (strips private keys, escalates the instruction)."""
    kw = {k: v for k, v in create_kwargs.items() if not k.startswith("_")}
    if attempt > 0 and "_base_messages" in create_kwargs:
        kw["messages"] = _add_system_instruction(create_kwargs["_base_messages"], _instruction(enf, attempt))
    return kw


def strip_private(create_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in create_kwargs.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Recovering tool calls the model printed as text
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json|tool_call|tool)?\s*\n?(.*?)```", re.DOTALL)
_TAG_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)


def _json_candidates(text: str) -> List[Any]:
    blobs = [m.group(1) for m in _TAG_RE.finditer(text)]
    blobs += [m.group(1) for m in _FENCE_RE.finditer(text)]
    blobs.append(text.strip())
    out: List[Any] = []
    for blob in blobs:
        blob = blob.strip()
        if not blob or blob[0] not in "[{":
            continue
        try:
            out.append(json.loads(blob))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def recover_tool_calls(text: str, tools: Optional[List[Dict[str, Any]]], enf: ToolEnforcement) -> List[Dict[str, Any]]:
    """Return OpenAI-style tool_calls recovered from ``text``, or [] if none are valid."""
    available = set(_tool_names(tools))
    for parsed in _json_candidates(text):
        items = parsed if isinstance(parsed, list) else [parsed]
        calls: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                calls = []
                break
            if isinstance(item.get("function"), dict):
                item = item["function"]
            name = item.get("name")
            args = item.get("arguments", item.get("parameters", item.get("input")))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = None
            if name not in available or not isinstance(args, dict):
                calls = []
                break
            calls.append({
                "id": f"call_{uuid.uuid4().hex[:24]}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            })
        if calls and any(enf.satisfied_by(c["function"]["name"]) for c in calls):
            return calls
    return []
