"""
FastMCP Tool Server for Musegix.
Exposes developer intelligence tools to bolt.diy and autonomous IDE agents:
1. polyfabric_symbol_search: AST symbol search across workspace files.
2. veylqora_memory_inspect: Evidence-anchored memory status verification (ACTIVE, SUSPECTED_STALE, EVIDENCE_MISSING).
3. ui_visual_render_gate: Real Playwright headless DOM layout & error verification gate.
"""

import ast
import hashlib
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP
from mcp_servers.render_gate import verify_webcontainer_dom

# Initialize FastMCP Server
mcp = FastMCP(
    "musegix",
    instructions="Musegix Autonomous AI IDE Gateway MCP Server providing AST search, anchored memory verification, and DOM layout validation.",
)

# Workspace Root
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# In-memory registry for Veylqora anchored symbol fingerprints
# Maps normalized file_path -> {"fingerprint": str, "timestamp": float, "symbols": list[str]}
_VEYLQORA_MEMORY_REGISTRY: Dict[str, Dict[str, Any]] = {}


def _resolve_path(file_path: str) -> Path:
    """Resolve file path relative to workspace root if not absolute."""
    p = Path(file_path)
    if not p.is_absolute():
        p = WORKSPACE_ROOT / p
    return p.resolve()


def _extract_python_symbols(source: str, file_rel: str) -> List[Dict[str, Any]]:
    """Extract class, function, and method signatures using Python's AST parser."""
    symbols = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({
                "name": node.name,
                "kind": "function" if not isinstance(node, ast.AsyncFunctionDef) else "async_function",
                "file": file_rel,
                "line": node.lineno,
                "signature": f"def {node.name}(...)",
            })
        elif isinstance(node, ast.ClassDef):
            symbols.append({
                "name": node.name,
                "kind": "class",
                "file": file_rel,
                "line": node.lineno,
                "signature": f"class {node.name}",
            })
    return symbols


_JS_TS_SYMBOL_PATTERNS = [
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)", re.M), "function"),
    (re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_$]+)", re.M), "class"),
    (re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", re.M), "interface"),
    (re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z0-9_$]+)\s*=", re.M), "type"),
    (re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.M), "arrow_function"),
]


def _extract_regex_symbols(source: str, file_rel: str) -> List[Dict[str, Any]]:
    """Extract symbol definitions for JS/TS/other languages via regex pattern matching."""
    symbols = []
    lines = source.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, kind in _JS_TS_SYMBOL_PATTERNS:
            match = pattern.search(line)
            if match:
                name = match.group(1)
                symbols.append({
                    "name": name,
                    "kind": kind,
                    "file": file_rel,
                    "line": idx,
                    "signature": line.strip()[:100],
                })
    return symbols


def extract_file_symbols(file_path: Path) -> List[Dict[str, Any]]:
    """Extract declared symbols from supported file types."""
    if not file_path.exists() or not file_path.is_file():
        return []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    try:
        rel_path = file_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        rel_path = file_path.as_posix()

    suffix = file_path.suffix.lower()
    if suffix == ".py":
        return _extract_python_symbols(content, rel_path)
    elif suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
        return _extract_regex_symbols(content, rel_path)
    return []


def calculate_symbol_fingerprint(file_path: Path) -> Tuple[Optional[str], List[str]]:
    """
    Computes a cryptographic fingerprint (SHA-256) of all symbol signatures in a file.
    Mutations to implementations that preserve symbol signatures do not mutate this fingerprint;
    only structural signature alterations (evidence invalidations) mutate the fingerprint.
    """
    symbols = extract_file_symbols(file_path)
    if not symbols:
        return None, []
    sig_strings = sorted(f"{s['kind']}:{s['name']}:{s['signature']}" for s in symbols)
    combined = "\n".join(sig_strings)
    fp = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    return fp, sig_strings


def anchor_veylqora_memory(file_path: str, custom_fingerprint: Optional[str] = None) -> Dict[str, Any]:
    """Helper function to explicitly anchor a file's symbol state in the Veylqora memory registry."""
    path = _resolve_path(file_path)
    normalized = path.as_posix()
    fp, sigs = calculate_symbol_fingerprint(path)
    final_fp = custom_fingerprint or fp or ""
    _VEYLQORA_MEMORY_REGISTRY[normalized] = {
        "fingerprint": final_fp,
        "timestamp": time.time(),
        "symbols": sigs,
    }
    return {
        "file_path": normalized,
        "anchored_fingerprint": final_fp,
        "symbols_tracked": len(sigs),
    }


def clear_veylqora_memory() -> None:
    """Clear memory registry (useful for testing and workspace turn resets)."""
    _VEYLQORA_MEMORY_REGISTRY.clear()


# ============================================================================
# MCP Tools Exposing FastMCP Endpoints
# ============================================================================


@mcp.tool()
async def polyfabric_symbol_search(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Searches indexed workspace AST symbols for targeted definitions matching query.

    Args:
        query: Symbol name, function, class, or definition identifier to find.
        top_k: Maximum number of ranked results to return (default 5).

    Returns:
        Dictionary containing matched symbols, file locations, line numbers, and signatures.
    """
    q = query.strip()
    if not q:
        return {"query": query, "top_k": top_k, "total_matches": 0, "symbols": []}

    target_extensions = {".py", ".ts", ".tsx", ".js", ".jsx"}
    ignore_dirs = {".git", ".pytest_cache", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}

    all_symbols: List[Dict[str, Any]] = []

    # Traverse workspace
    for root, dirs, files in os.walk(WORKSPACE_ROOT):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in target_extensions:
                syms = extract_file_symbols(p)
                all_symbols.extend(syms)

    q_lower = q.lower()
    matches = []
    for s in all_symbols:
        name_lower = s["name"].lower()
        if q_lower in name_lower or name_lower in q_lower:
            # Score: exact match = 0, starts with = 1, substring = 2
            if name_lower == q_lower:
                score = 0
            elif name_lower.startswith(q_lower):
                score = 1
            else:
                score = 2
            matches.append((score, s))

    matches.sort(key=lambda item: (item[0], len(item[1]["name"])))
    results = [item[1] for item in matches[:top_k]]

    return {
        "query": query,
        "top_k": top_k,
        "total_matches": len(matches),
        "symbols": results,
    }


@mcp.tool()
async def veylqora_memory_inspect(file_path: str) -> Dict[str, Any]:
    """
    Inspects anchored memory states for a given file: ACTIVE, SUSPECTED_STALE, or EVIDENCE_MISSING.
    Detects when workspace code cited in prior turns has mutated its AST symbol fingerprint.

    Args:
        file_path: Relative or absolute path to the workspace file to inspect.

    Returns:
        Dictionary with status ('ACTIVE', 'SUSPECTED_STALE', or 'EVIDENCE_MISSING') and diagnostic details.
    """
    path = _resolve_path(file_path)
    normalized = path.as_posix()

    if not path.exists() or not path.is_file():
        return {
            "file_path": file_path,
            "status": "EVIDENCE_MISSING",
            "fingerprint": None,
            "anchored_fingerprint": None,
            "symbols_tracked": 0,
            "details": f"Evidence missing: file '{file_path}' does not exist on disk.",
        }

    current_fp, sigs = calculate_symbol_fingerprint(path)
    if not current_fp:
        return {
            "file_path": file_path,
            "status": "EVIDENCE_MISSING",
            "fingerprint": None,
            "anchored_fingerprint": None,
            "symbols_tracked": 0,
            "details": f"Evidence missing: no declared AST symbols found in '{file_path}'.",
        }

    # Check if previously anchored
    if normalized in _VEYLQORA_MEMORY_REGISTRY:
        anchored_entry = _VEYLQORA_MEMORY_REGISTRY[normalized]
        anchored_fp = anchored_entry["fingerprint"]
        if current_fp == anchored_fp:
            status = "ACTIVE"
            details = "Symbol fingerprint verified. Anchored memory is active and consistent."
        else:
            status = "SUSPECTED_STALE"
            details = (
                f"SUSPECTED_STALE: AST symbol fingerprint mutated from "
                f"{anchored_fp[:8]}... to {current_fp[:8]}... across workspace turns."
            )
    else:
        # Auto-anchor baseline for file upon first observation
        _VEYLQORA_MEMORY_REGISTRY[normalized] = {
            "fingerprint": current_fp,
            "timestamp": time.time(),
            "symbols": sigs,
        }
        anchored_fp = current_fp
        status = "ACTIVE"
        details = "Baseline symbol fingerprint established and anchored."

    return {
        "file_path": file_path,
        "status": status,
        "fingerprint": current_fp,
        "anchored_fingerprint": anchored_fp,
        "symbols_tracked": len(sigs),
        "details": details,
    }


@mcp.tool()
async def ui_visual_render_gate(
    preview_url: str = "http://localhost:5173",
    timeout_ms: int = 8000,
) -> Dict[str, Any]:
    """
    Executes headless Playwright DOM layout verification gate against the WebContainer preview.

    Verifies:
    - HTTP/Network reachability
    - Zero console errors and uncaught exceptions
    - No horizontal layout collisions (scrollWidth <= innerWidth)
    - Interactive elements mounted and visible

    Args:
        preview_url: The preview URL to navigate to (default: http://localhost:5173).
        timeout_ms: Maximum navigation timeout in milliseconds (default: 8000).

    Returns:
        Status ('PASSED', 'FAILED', or 'UNAVAILABLE') with metrics and diagnostic console traces.
    """
    return await verify_webcontainer_dom(preview_url=preview_url, timeout_ms=timeout_ms)


if __name__ == "__main__":
    # Runs the FastMCP server over stdio for bolt.diy or agent integration
    mcp.run()
