"""Per-chat symbol index for PolyFabric: functions, classes and components with line ranges.

The index learns from project_read_file results and project_write_file calls in the request
history, keyed by chat id. It is rendered as a compact map (one line per file) that the gateway
injects into the system message, so the agent can patch a named symbol without reading the file.

Line ranges come from the file as it was last seen. Python uses the stdlib ast module. TS/JS uses
a line scanner with brace matching: it is an approximation for the common shapes (function, class,
const arrow/function components) and does not parse JSX or template literals exactly.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from gateway.engines.polyfabric_pruner import count_tokens
from gateway.engines.tool_result_pruner import is_failed_tool_result

READ_TOOL = "project_read_file"
WRITE_TOOL = "project_write_file"
PRUNED_MARKER = "[PolyFabric: old tool output pruned"
TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
MAX_CHATS = 200

_FN = re.compile(r"^(\s*)(export\s+)?(default\s+)?(async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)")
_CLASS = re.compile(r"^(\s*)(export\s+)?(default\s+)?(abstract\s+)?class\s+([A-Za-z_$][\w$]*)")
_CONST_FN = re.compile(
    r"^(\s*)(export\s+)?const\s+([A-Za-z_$][\w$]*)\b[^=]*=\s*(async\s+)?"
    r"(\(|function\b|[A-Za-z_$][\w$]*\s*=>)"
)
_STRING = re.compile(r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)")


@dataclass
class SymbolRange:
    name: str
    kind: str  # "function", "class", "component", "method"
    start: int  # 1-based
    end: int
    exported: bool = False


@dataclass
class FileEntry:
    path: str
    content: str
    digest: str
    symbols: List[SymbolRange] = field(default_factory=list)


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _block_end(lines: List[str], idx: int) -> int:
    """1-based end line of the block that opens at lines[idx] (brace matching, approximate)."""
    depth = 0
    started = False
    paren = 0
    for j in range(idx, len(lines)):
        code = _STRING.sub("''", lines[j])
        code = re.sub(r"//.*$", "", code)
        for ch in code:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
            elif ch == "(":
                paren += 1
            elif ch == ")":
                paren -= 1
        if started and depth <= 0:
            return j + 1
        if not started and paren <= 0 and code.rstrip().endswith((";", ")")) and j > idx:
            return j + 1
    return len(lines)


def _ts_js_symbols(content: str) -> List[SymbolRange]:
    lines = content.splitlines()
    out: List[SymbolRange] = []
    seen = set()
    for idx, line in enumerate(lines):
        if line[:1] in (" ", "\t") and not line.lstrip().startswith("export"):
            # Only top-level declarations are indexed (nested helpers stay inside their parent).
            continue
        name = kind = None
        exported = False
        m = _FN.match(line)
        if m:
            name, kind, exported = m.group(5), "function", bool(m.group(2))
        else:
            m = _CLASS.match(line)
            if m:
                name, kind, exported = m.group(5), "class", bool(m.group(2))
            else:
                m = _CONST_FN.match(line)
                if m:
                    name = m.group(3)
                    kind = "component" if name[:1].isupper() else "function"
                    exported = bool(m.group(2))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(SymbolRange(name, kind, idx + 1, _block_end(lines, idx), exported))
    return out


def _py_symbols(content: str) -> List[SymbolRange]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    out: List[SymbolRange] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(SymbolRange(node.name, "function", node.lineno, node.end_lineno or node.lineno,
                              not node.name.startswith("_")))
        elif isinstance(node, ast.ClassDef):
            out.append(SymbolRange(node.name, "class", node.lineno, node.end_lineno or node.lineno,
                              not node.name.startswith("_")))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(SymbolRange(f"{node.name}.{item.name}", "method", item.lineno,
                                      item.end_lineno or item.lineno, not item.name.startswith("_")))
    return out


def extract_symbols(path: str, content: str) -> List[SymbolRange]:
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    if "." + ext == ".py":
        return _py_symbols(content)
    if "." + ext in TS_EXTS:
        return _ts_js_symbols(content)
    return []


def _tool_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def _read_content(text: str) -> Optional[str]:
    """File body from a project_read_file result (JSON with a content key, or raw text)."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    if isinstance(data, dict) and isinstance(data.get("content"), str):
        return data["content"]
    return None


class SymbolIndex:
    """SymbolRange map for one chat."""

    def __init__(self) -> None:
        self._files: Dict[str, FileEntry] = {}

    def __len__(self) -> int:
        return len(self._files)

    def observe(self, path: str, content: str) -> str:
        """Record a file's current content. Returns "new", "changed" or "unchanged"."""
        digest = content_hash(content)
        entry = self._files.get(path)
        if entry is None:
            self._files[path] = FileEntry(path, content, digest, extract_symbols(path, content))
            return "new"
        if entry.digest == digest:
            return "unchanged"
        self._files[path] = FileEntry(path, content, digest, extract_symbols(path, content))
        return "changed"

    def apply_patch(self, path: str, old_text: str, new_text: str) -> str:
        """Apply one exact oldText -> newText replacement to a known file.

        Returns "changed" when the file is known and oldText occurs exactly once, otherwise "miss".
        The index is updated at generation time; a later read of the file corrects it if the
        patch did not apply in bolt.
        """
        entry = self._files.get(path)
        if entry is None or not old_text or entry.content.count(old_text) != 1:
            return "miss"
        self.observe(path, entry.content.replace(old_text, new_text, 1))
        return "changed"

    def digest(self, path: str) -> Optional[str]:
        entry = self._files.get(path)
        return entry.digest if entry else None

    def symbols(self, path: str) -> List[SymbolRange]:
        entry = self._files.get(path)
        return list(entry.symbols) if entry else []

    def files(self) -> Dict[str, str]:
        return {p: e.content for p, e in self._files.items()}

    def ingest_messages(self, messages: Iterable[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        """Learn from project_write_file calls and project_read_file results in the history.

        Only the last state of each file in the history is applied, so replaying the same history
        on every request reports no changes. Returns (changed_paths, new_paths).
        """
        msgs = [m for m in messages if isinstance(m, dict)]
        calls: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        latest: "OrderedDict[str, str]" = OrderedDict()

        for m in msgs:
            if m.get("role") == "assistant":
                for tc in m.get("tool_calls") or []:
                    fn = (tc or {}).get("function") or {}
                    name = fn.get("name")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(args, dict):
                        continue
                    calls[tc.get("id", "")] = (name, args)
                    if name == WRITE_TOOL and isinstance(args.get("path"), str) \
                            and isinstance(args.get("content"), str):
                        latest[args["path"]] = args["content"]

        for m in msgs:
            if m.get("role") != "tool":
                continue
            name, args = calls.get(m.get("tool_call_id", ""), (None, {}))
            path = args.get("path")
            if name != READ_TOOL or not isinstance(path, str):
                continue
            text = _tool_text(m.get("content"))
            if not text or PRUNED_MARKER in text or is_failed_tool_result(text):
                continue
            body = _read_content(text)
            if body is not None:
                latest[path] = body

        changed: List[str] = []
        new: List[str] = []
        for path, content in latest.items():
            result = self.observe(path, content)
            if result == "changed":
                changed.append(path)
            elif result == "new":
                new.append(path)
        return changed, new

    def compact_map(self, max_tokens: int = 500) -> str:
        """One line per file with its top-level symbols, within max_tokens.

        Example: "src/pages/Settings.tsx: SettingsPage L10-180, ApiKeysCard L182-240"
        """
        lines: List[str] = []
        for path in sorted(self._files):
            top = [s for s in self._files[path].symbols if s.kind != "method"]
            if not top:
                continue
            line = f"{path}: " + ", ".join(f"{s.name} L{s.start}-{s.end}" for s in top)
            candidate = "\n".join(lines + [line])
            if count_tokens(candidate) > max_tokens:
                break
            lines.append(line)
        return "\n".join(lines)

    def exported_names(self, path: str) -> List[str]:
        return [s.name for s in self.symbols(path) if s.exported and s.kind != "method"]


_INDEXES: "OrderedDict[str, SymbolIndex]" = OrderedDict()


def index_for_chat(chat_id: str) -> SymbolIndex:
    """Per-chat index. Each chat id gets its own map; the oldest chats are evicted past MAX_CHATS."""
    idx = _INDEXES.get(chat_id)
    if idx is None:
        idx = SymbolIndex()
        _INDEXES[chat_id] = idx
        while len(_INDEXES) > MAX_CHATS:
            _INDEXES.popitem(last=False)
    return idx


def reset_indexes() -> None:
    _INDEXES.clear()


SYMBOL_MAP_HEADER = (
    "PolyFabric symbol map (file: symbol line ranges). When the target symbol is listed here, "
    "patch it by name instead of reading the whole file first:"
)


def inject_symbol_map(messages: List[Dict[str, Any]], symbol_map: str) -> List[Dict[str, Any]]:
    """Append the map to the system message (a new one is created if none exists). No-op when empty."""
    if not symbol_map:
        return messages
    block = f"\n\n{SYMBOL_MAP_HEADER}\n{symbol_map}"
    out = list(messages)
    for i, m in enumerate(out):
        if isinstance(m, dict) and m.get("role") == "system":
            content = m.get("content") if isinstance(m.get("content"), str) else ""
            out[i] = {**m, "content": content + block}
            return out
    return [{"role": "system", "content": block.lstrip()}] + out
