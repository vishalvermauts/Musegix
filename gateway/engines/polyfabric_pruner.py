"""PolyFabric Safe Context Pruner for Musegix Gateway.

Invariants:
1. Target File Invariant: The file being edited must NEVER have its body truncated
   or modified. It must retain 100% full content inside <boltAction type="file" filePath="...">
   tags so bolt.diy WebContainer can build and execute it.
2. Background Files: Non-targeted background files are pruned into compact AST symbol
   signatures (exported functions, classes, interfaces, types, and imports).
3. Token Measurements: Real token and character counts measured with tiktoken.
   Zero fake constants or hardcoded multipliers (* 0.14 or 90.8%).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import os
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
    try:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _ENCODER = None
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    _ENCODER = None

# Tree-sitter imports for TypeScript, TSX, and JavaScript
_TREE_SITTER_AVAILABLE = False
_TS_PARSER = None
_TSX_PARSER = None
_JS_PARSER = None

try:
    import tree_sitter
    import tree_sitter_typescript
    import tree_sitter_javascript

    _TS_LANG = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    _TSX_LANG = tree_sitter.Language(tree_sitter_typescript.language_tsx())
    _JS_LANG = tree_sitter.Language(tree_sitter_javascript.language())

    _TS_PARSER = tree_sitter.Parser(_TS_LANG)
    _TSX_PARSER = tree_sitter.Parser(_TSX_LANG)
    _JS_PARSER = tree_sitter.Parser(_JS_LANG)
    _TREE_SITTER_AVAILABLE = True
except Exception:
    _TREE_SITTER_AVAILABLE = False


@dataclass
class PruneResult:
    """Telemetry and measurement metrics resulting from context pruning."""
    pruned_text: str
    raw_tokens: int
    pruned_tokens: int
    saved_tokens: int
    reduction_pct: float
    raw_chars: int
    pruned_chars: int
    target_files: List[str] = field(default_factory=list)
    pruned_files: List[str] = field(default_factory=list)
    preserved_files: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_tokens": self.raw_tokens,
            "pruned_tokens": self.pruned_tokens,
            "saved_tokens": self.saved_tokens,
            "reduction_pct": self.reduction_pct,
            "raw_chars": self.raw_chars,
            "pruned_chars": self.pruned_chars,
            "target_files": self.target_files,
            "pruned_files": self.pruned_files,
            "preserved_files": self.preserved_files,
            "elapsed_ms": self.elapsed_ms,
        }


def count_tokens(text: str) -> int:
    """Measure real token count of text using tiktoken cl100k_base encoder.

    Falls back to whitespace/punctuation splitting if tiktoken is unavailable.
    Never uses a hardcoded multiplier.
    """
    if not text:
        return 0
    if _ENCODER is not None:
        try:
            return len(_ENCODER.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Fallback to whitespace/sub-word count
    tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
    return max(1, len(tokens))


def _extract_ts_js_signatures(code: str, file_path: str) -> str:
    """Extract AST symbol signatures from TypeScript / TSX / JavaScript code.

    Keeps:
    - import statements
    - interface declarations
    - type alias declarations
    - enum declarations
    - exported function signatures (with bodies stubbed)
    - exported class declarations (with fields and method signatures; bodies stubbed)
    - exported const / variable declarations
    """
    if not _TREE_SITTER_AVAILABLE or not code.strip():
        # Fallback regex-based signature extraction if tree-sitter is missing
        return _extract_signatures_regex_fallback(code)

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".tsx":
        parser = _TSX_PARSER
    elif ext in (".ts", ".mts", ".cts"):
        parser = _TS_PARSER
    else:
        parser = _JS_PARSER or _TSX_PARSER

    try:
        tree = parser.parse(code.encode("utf-8"))
    except Exception:
        return _extract_signatures_regex_fallback(code)

    signatures: List[str] = []
    signatures.append("// [PolyFabric AST Pruned] Exported signatures preserved for context")

    def node_text(n: Any) -> str:
        return n.text.decode("utf-8", errors="replace")

    for child in tree.root_node.children:
        t = child.type
        # Keep comments and imports
        if t == "import_statement":
            signatures.append(node_text(child))
        elif t in ("interface_declaration", "type_alias_declaration", "enum_declaration"):
            signatures.append(node_text(child))
        elif t == "export_statement":
            # Extract exported declarations
            exported_parts: List[str] = []
            for sub in child.children:
                st = sub.type
                if st in ("interface_declaration", "type_alias_declaration", "enum_declaration"):
                    exported_parts.append(node_text(sub))
                elif st == "function_declaration":
                    name_node = sub.child_by_field_name("name")
                    params_node = sub.child_by_field_name("parameters")
                    ret_node = sub.child_by_field_name("return_type")
                    name = node_text(name_node) if name_node else "fn"
                    params = node_text(params_node) if params_node else "()"
                    ret = (" " + node_text(ret_node)) if ret_node else ""
                    exported_parts.append(f"function {name}{params}{ret};")
                elif st == "class_declaration":
                    cname_node = sub.child_by_field_name("name")
                    cname = node_text(cname_node) if cname_node else "Anonymous"
                    body_node = sub.child_by_field_name("body")
                    method_sigs: List[str] = []
                    if body_node:
                        for m in body_node.children:
                            if m.type == "method_definition":
                                m_name = m.child_by_field_name("name")
                                m_params = m.child_by_field_name("parameters")
                                m_ret = m.child_by_field_name("return_type")
                                mn = node_text(m_name) if m_name else ""
                                mp = node_text(m_params) if m_params else "()"
                                mr = (" " + node_text(m_ret)) if m_ret else ""
                                method_sigs.append(f"  {mn}{mp}{mr};")
                            elif m.type in ("public_field_definition", "property_signature"):
                                method_sigs.append(f"  {node_text(m)}")
                    exported_parts.append(f"class {cname} {{\n" + "\n".join(method_sigs) + "\n}")
                elif st == "lexical_declaration":
                    # const Foo = ... or const Foo: React.FC<Props> = ...
                    decl_text = node_text(sub)
                    # Strip implementation body if it assigns a function or component
                    if "=" in decl_text:
                        lhs = decl_text.split("=")[0].strip()
                        exported_parts.append(f"{lhs};")
                    else:
                        exported_parts.append(decl_text)
            if exported_parts:
                signatures.append("export " + " ".join(exported_parts))
            else:
                signatures.append(node_text(child))
        elif t == "function_declaration":
            # Non-exported top-level function declaration
            name_node = child.child_by_field_name("name")
            params_node = child.child_by_field_name("parameters")
            ret_node = child.child_by_field_name("return_type")
            name = node_text(name_node) if name_node else "fn"
            params = node_text(params_node) if params_node else "()"
            ret = (" " + node_text(ret_node)) if ret_node else ""
            signatures.append(f"function {name}{params}{ret};")
        elif t == "class_declaration":
            cname_node = child.child_by_field_name("name")
            cname = node_text(cname_node) if cname_node else "Anonymous"
            body_node = child.child_by_field_name("body")
            method_sigs = []
            if body_node:
                for m in body_node.children:
                    if m.type == "method_definition":
                        m_name = m.child_by_field_name("name")
                        m_params = m.child_by_field_name("parameters")
                        m_ret = m.child_by_field_name("return_type")
                        mn = node_text(m_name) if m_name else ""
                        mp = node_text(m_params) if m_params else "()"
                        mr = (" " + node_text(m_ret)) if m_ret else ""
                        method_sigs.append(f"  {mn}{mp}{mr};")
                    elif m.type in ("public_field_definition", "property_signature"):
                        method_sigs.append(f"  {node_text(m)}")
            signatures.append(f"class {cname} {{\n" + "\n".join(method_sigs) + "\n}")

    result = "\n\n".join(signatures).strip()
    return result if len(result) > len(signatures[0]) else _extract_signatures_regex_fallback(code)


def _extract_py_signatures(code: str) -> str:
    """Extract AST symbol signatures from Python code using Python's standard library ast."""
    try:
        tree = ast.parse(code)
    except Exception:
        return _extract_signatures_regex_fallback(code)

    new_body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            new_body.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
            new_body.append(node)
        elif isinstance(node, ast.ClassDef):
            class_methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
                    class_methods.append(item)
                elif isinstance(item, (ast.AnnAssign, ast.Assign)):
                    class_methods.append(item)
            node.body = class_methods or [ast.Pass()]
            new_body.append(node)

    tree.body = new_body
    ast.fix_missing_locations(tree)
    try:
        unparsed = ast.unparse(tree)
        return "# [PolyFabric AST Pruned] Signatures preserved for context\n" + unparsed
    except Exception:
        return _extract_signatures_regex_fallback(code)


def _extract_signatures_regex_fallback(code: str) -> str:
    """Fallback signature extractor using regular expressions if AST parsing is not possible."""
    lines = code.splitlines()
    preserved_lines: List[str] = [
        "// [PolyFabric AST Pruned] Summary signatures preserved"
    ]
    for line in lines:
        stripped = line.strip()
        # Keep imports, interfaces, types, exports, function headers, class headers
        if (
            stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("export interface ")
            or stripped.startswith("export type ")
            or stripped.startswith("export enum ")
            or stripped.startswith("export const ")
            or stripped.startswith("export function ")
            or stripped.startswith("export class ")
            or stripped.startswith("function ")
            or stripped.startswith("def ")
            or stripped.startswith("class ")
            or stripped.startswith("@")
        ):
            # If line opens a block, replace block body with stub
            if "{" in line and not stripped.startswith("import"):
                header = line.split("{")[0].strip()
                preserved_lines.append(f"{header} {{ /* pruned */ }}")
            elif line.rstrip().endswith(":"):
                preserved_lines.append(f"{line}\n    ...")
            else:
                preserved_lines.append(line)
    return "\n".join(preserved_lines)


class PolyFabricPruner:
    """Safe context pruner adhering strictly to the Target File Invariant."""

    def __init__(self) -> None:
        pass

    def count_tokens(self, text: str) -> int:
        """Measure real tokens of text."""
        return count_tokens(text)

    def prune_file(self, file_path: str, content: str) -> str:
        """Prune a single background file's content to AST symbol signatures."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            return _extract_ts_js_signatures(content, file_path)
        elif ext == ".py":
            return _extract_py_signatures(content)
        elif ext == ".json":
            # For JSON, preserve top-level keys or truncated preview
            lines = content.splitlines()
            if len(lines) > 20:
                return "\n".join(lines[:10]) + "\n  // ... [PolyFabric pruned JSON entries] ...\n" + "\n".join(lines[-3:])
            return content
        else:
            # Generic fallback: keep first 15 lines if long
            lines = content.splitlines()
            if len(lines) > 25:
                return "\n".join(lines[:15]) + f"\n// ... [PolyFabric pruned {len(lines) - 15} lines] ..."
            return content

    def detect_target_files(
        self,
        prompt: str,
        available_files: Sequence[str]
    ) -> List[str]:
        """Detect the active target file(s) being referenced in the user prompt.

        Matches exact file paths and basenames (e.g. 'App.tsx' matching 'src/App.tsx').
        """
        targets: List[str] = []
        if not prompt or not available_files:
            return targets

        prompt_clean = prompt.replace("\\", "/")

        for file_path in available_files:
            norm_path = file_path.replace("\\", "/").strip()
            basename = os.path.basename(norm_path)

            # Check full path match
            if re.search(r"\b" + re.escape(norm_path) + r"\b", prompt_clean, re.IGNORECASE):
                targets.append(file_path)
                continue

            # Check basename match (e.g. 'App.tsx')
            if basename and re.search(r"\b" + re.escape(basename) + r"\b", prompt_clean, re.IGNORECASE):
                targets.append(file_path)

        return targets

    def prune_context(
        self,
        context_text: str,
        target_file: Optional[str] = None,
        target_files: Optional[Sequence[str]] = None,
        user_prompt: Optional[str] = None,
    ) -> PruneResult:
        """Prune context text containing <boltAction type="file" filePath="..."> blocks.

        INVARIANT:
        The target file(s) MUST NEVER have their bodies modified or truncated.
        Target files remain 100% byte-for-byte intact inside their <boltAction> tags.
        Only background files are replaced with compact AST symbol signatures.
        """
        t0 = time.perf_counter()

        # Parse all <boltAction ...> blocks
        action_pattern = re.compile(
            r'(<boltAction\s+([^>]*?)>)([\s\S]*?)(</boltAction>)',
            re.IGNORECASE
        )

        all_blocks = list(action_pattern.finditer(context_text))

        # Collect available file paths from boltAction tags
        available_files: List[str] = []
        for m in all_blocks:
            attrs = m.group(2)
            type_m = re.search(r'type=["\']([^"\']+)["\']', attrs)
            path_m = re.search(r'filePath=["\']([^"\']+)["\']', attrs)
            if type_m and type_m.group(1).lower() == "file" and path_m:
                available_files.append(path_m.group(1).strip())

        # Determine target file set
        resolved_targets: Set[str] = set()
        if target_file:
            resolved_targets.add(target_file.strip())
        if target_files:
            for tf in target_files:
                resolved_targets.add(tf.strip())

        # If no explicit target provided, auto-detect from user_prompt
        if not resolved_targets and user_prompt:
            detected = self.detect_target_files(user_prompt, available_files)
            for d in detected:
                resolved_targets.add(d)

        # Helper to check if a file_path matches any resolved target
        def is_target(fp: str) -> bool:
            norm_fp = fp.replace("\\", "/").strip()
            base_fp = os.path.basename(norm_fp)
            for t in resolved_targets:
                norm_t = t.replace("\\", "/").strip()
                if norm_fp == norm_t or base_fp == os.path.basename(norm_t):
                    return True
            return False

        # If no target could be determined, fail-safe:
        # Preserve all files rather than accidentally truncating the user's active edit file
        pruned_files: List[str] = []
        preserved_files: List[str] = []

        # Build replacement string
        last_idx = 0
        output_parts: List[str] = []

        for m in all_blocks:
            open_tag = m.group(1)
            attrs = m.group(2)
            body = m.group(3)
            close_tag = m.group(4)
            start_pos = m.start()

            # Append preceding unpruned text
            output_parts.append(context_text[last_idx:start_pos])

            type_m = re.search(r'type=["\']([^"\']+)["\']', attrs)
            path_m = re.search(r'filePath=["\']([^"\']+)["\']', attrs)

            if type_m and type_m.group(1).lower() == "file" and path_m:
                file_path = path_m.group(1).strip()
                if is_target(file_path) or not resolved_targets:
                    # TARGET FILE INVARIANT: 100% UNTOUCHED
                    output_parts.append(open_tag + body + close_tag)
                    preserved_files.append(file_path)
                else:
                    # BACKGROUND FILE: Prune to AST symbol signatures
                    pruned_body = self.prune_file(file_path, body)
                    output_parts.append(open_tag + "\n" + pruned_body + "\n" + close_tag)
                    pruned_files.append(file_path)
            else:
                # Non-file boltAction (e.g. shell command) -> keep intact
                output_parts.append(open_tag + body + close_tag)

            last_idx = m.end()

        # Append remaining context
        output_parts.append(context_text[last_idx:])
        pruned_text = "".join(output_parts)

        # Real measurements without hardcoded multipliers
        raw_chars = len(context_text)
        pruned_chars = len(pruned_text)
        raw_tokens = count_tokens(context_text)
        pruned_tokens = count_tokens(pruned_text)
        saved_tokens = max(0, raw_tokens - pruned_tokens)
        reduction_pct = round((1.0 - (pruned_tokens / raw_tokens)) * 100.0, 2) if raw_tokens > 0 else 0.0
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        return PruneResult(
            pruned_text=pruned_text,
            raw_tokens=raw_tokens,
            pruned_tokens=pruned_tokens,
            saved_tokens=saved_tokens,
            reduction_pct=reduction_pct,
            raw_chars=raw_chars,
            pruned_chars=pruned_chars,
            target_files=list(resolved_targets),
            pruned_files=pruned_files,
            preserved_files=preserved_files,
            elapsed_ms=elapsed_ms,
        )

    def prune_payload(
        self,
        payload: dict,
        target_file: Optional[str] = None
    ) -> Tuple[dict, PruneResult]:
        """Prune an OpenAI chat completions payload.

        Analyzes messages, extracts the user prompt to detect target files,
        and prunes background files in context messages.
        """
        messages = payload.get("messages", [])
        if not messages:
            empty_res = PruneResult(
                pruned_text="", raw_tokens=0, pruned_tokens=0, saved_tokens=0,
                reduction_pct=0.0, raw_chars=0, pruned_chars=0
            )
            return payload, empty_res

        # Extract latest user message to detect target file
        user_prompt = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, str):
                    user_prompt = content
                elif isinstance(content, list):
                    # Multi-part content
                    texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    user_prompt = "\n".join(texts)
                break

        # Collect total raw tokens and characters across all messages
        total_raw_chars = 0
        total_pruned_chars = 0
        total_raw_tokens = 0
        total_pruned_tokens = 0
        all_target_files: Set[str] = set()
        all_pruned_files: Set[str] = set()
        all_preserved_files: Set[str] = set()

        new_messages = []
        t0 = time.perf_counter()

        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str) and "<boltAction" in content:
                res = self.prune_context(
                    context_text=content,
                    target_file=target_file,
                    user_prompt=user_prompt,
                )
                new_msg = dict(m)
                new_msg["content"] = res.pruned_text
                new_messages.append(new_msg)

                total_raw_chars += res.raw_chars
                total_pruned_chars += res.pruned_chars
                total_raw_tokens += res.raw_tokens
                total_pruned_tokens += res.pruned_tokens
                all_target_files.update(res.target_files)
                all_pruned_files.update(res.pruned_files)
                all_preserved_files.update(res.preserved_files)
            else:
                new_messages.append(m)
                msg_str = content if isinstance(content, str) else str(content)
                chars = len(msg_str)
                tokens = count_tokens(msg_str)
                total_raw_chars += chars
                total_pruned_chars += chars
                total_raw_tokens += tokens
                total_pruned_tokens += tokens

        saved_tokens = max(0, total_raw_tokens - total_pruned_tokens)
        reduction_pct = (
            round((1.0 - (total_pruned_tokens / total_raw_tokens)) * 100.0, 2)
            if total_raw_tokens > 0 else 0.0
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        new_payload = dict(payload)
        new_payload["messages"] = new_messages

        combined_result = PruneResult(
            pruned_text="",
            raw_tokens=total_raw_tokens,
            pruned_tokens=total_pruned_tokens,
            saved_tokens=saved_tokens,
            reduction_pct=reduction_pct,
            raw_chars=total_raw_chars,
            pruned_chars=total_pruned_chars,
            target_files=list(all_target_files),
            pruned_files=list(all_pruned_files),
            preserved_files=list(all_preserved_files),
            elapsed_ms=elapsed_ms,
        )

        return new_payload, combined_result
