"""
Unit tests for Musegix FastMCP tool server and Playwright DOM layout verification gate.
Verifies MCP tool schemas, tool execution, and headless Playwright DOM checks
against offline HTML fixtures and unreachable endpoints.
"""

import os
import tempfile
import pytest
from pathlib import Path

from mcp_servers.musegix_mcp import (
    mcp,
    polyfabric_symbol_search,
    veylqora_memory_inspect,
    ui_visual_render_gate,
    anchor_veylqora_memory,
    clear_veylqora_memory,
)
from mcp_servers.render_gate import verify_webcontainer_dom


# ============================================================================
# MCP Server Tool Schema Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fastmcp_tool_registration_and_schemas():
    """Verify that all three required tools are registered with correct schemas."""
    tools = await mcp.list_tools()
    tool_map = {t.name: t for t in tools}

    assert "polyfabric_symbol_search" in tool_map, "polyfabric_symbol_search must be exposed"
    assert "veylqora_memory_inspect" in tool_map, "veylqora_memory_inspect must be exposed"
    assert "ui_visual_render_gate" in tool_map, "ui_visual_render_gate must be exposed"

    # 1. polyfabric_symbol_search schema
    poly_tool = tool_map["polyfabric_symbol_search"]
    poly_schema = poly_tool.inputSchema
    assert poly_schema["type"] == "object"
    assert "query" in poly_schema["properties"]
    assert poly_schema["properties"]["query"]["type"] == "string"
    assert "query" in poly_schema["required"]
    assert "top_k" in poly_schema["properties"]

    # 2. veylqora_memory_inspect schema
    veyl_tool = tool_map["veylqora_memory_inspect"]
    veyl_schema = veyl_tool.inputSchema
    assert veyl_schema["type"] == "object"
    assert "file_path" in veyl_schema["properties"]
    assert veyl_schema["properties"]["file_path"]["type"] == "string"
    assert "file_path" in veyl_schema["required"]

    # 3. ui_visual_render_gate schema
    render_tool = tool_map["ui_visual_render_gate"]
    render_schema = render_tool.inputSchema
    assert render_schema["type"] == "object"
    assert "preview_url" in render_schema["properties"]


@pytest.mark.asyncio
async def test_fastmcp_call_tool_dispatch():
    """Verify tools can be invoked via MCP call_tool protocol."""
    # Call polyfabric_symbol_search over MCP call_tool
    content_list, res_dict = await mcp.call_tool("polyfabric_symbol_search", {"query": "verify_webcontainer_dom"})
    assert len(content_list) > 0
    # FastMCP wraps tool output in {'result': ...}
    payload = res_dict.get("result", res_dict)
    assert "symbols" in payload
    assert payload["total_matches"] >= 1

    # Call veylqora_memory_inspect over MCP call_tool
    content_list, res_dict = await mcp.call_tool("veylqora_memory_inspect", {"file_path": "nonexistent_file_xyz.py"})
    payload = res_dict.get("result", res_dict)
    assert payload["status"] == "EVIDENCE_MISSING"


# ============================================================================
# PolyFabric Symbol Search Tests
# ============================================================================


@pytest.mark.asyncio
async def test_polyfabric_symbol_search_hit_and_bounding():
    """Verify AST symbol search finds genuine symbols and respects top_k bounding."""
    result = await polyfabric_symbol_search(query="verify_webcontainer_dom", top_k=5)
    assert result["query"] == "verify_webcontainer_dom"
    assert result["total_matches"] >= 1
    matched_names = [s["name"] for s in result["symbols"]]
    assert "verify_webcontainer_dom" in matched_names
    assert len(result["symbols"]) <= 5

    # Check structure of matched symbol
    sym = result["symbols"][0]
    assert "file" in sym
    assert "line" in sym
    assert "kind" in sym
    assert "signature" in sym


@pytest.mark.asyncio
async def test_polyfabric_symbol_search_empty_and_miss():
    """Verify symbol search handles empty queries and non-existent identifiers."""
    empty_res = await polyfabric_symbol_search(query="", top_k=5)
    assert empty_res["total_matches"] == 0
    assert empty_res["symbols"] == []

    miss_res = await polyfabric_symbol_search(query="completely_nonexistent_symbol_12345", top_k=5)
    assert miss_res["total_matches"] == 0
    assert miss_res["symbols"] == []


# ============================================================================
# Veylqora Evidence-Anchored Memory Tests
# ============================================================================


@pytest.mark.asyncio
async def test_veylqora_memory_inspect_lifecycle():
    """Verify ACTIVE, SUSPECTED_STALE, and EVIDENCE_MISSING states."""
    clear_veylqora_memory()

    # 1. Missing file -> EVIDENCE_MISSING
    res_missing = await veylqora_memory_inspect("path/does/not/exist.py")
    assert res_missing["status"] == "EVIDENCE_MISSING"

    # 2. Existing file with AST symbols -> ACTIVE (initial baseline)
    target_file = "mcp_servers/render_gate.py"
    res_active = await veylqora_memory_inspect(target_file)
    assert res_active["status"] == "ACTIVE"
    assert res_active["fingerprint"] is not None
    assert res_active["symbols_tracked"] > 0

    # 3. Subsequent inspect without changes remains ACTIVE
    res_active2 = await veylqora_memory_inspect(target_file)
    assert res_active2["status"] == "ACTIVE"
    assert res_active2["fingerprint"] == res_active["fingerprint"]

    # 4. Mutated anchor fingerprint -> SUSPECTED_STALE
    anchor_veylqora_memory(target_file, custom_fingerprint="mutated_prior_turn_fingerprint")
    res_stale = await veylqora_memory_inspect(target_file)
    assert res_stale["status"] == "SUSPECTED_STALE"
    assert "mutated" in res_stale["details"]


# ============================================================================
# Playwright Headless DOM Verification Gate Tests (Offline Fixtures)
# ============================================================================


@pytest.mark.asyncio
async def test_render_gate_passed_on_valid_page():
    """Verify PASSED status on a clean DOM fixture with visible interactive elements."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Preview Test</title>
    <style>
        body { margin: 0; padding: 20px; font-family: sans-serif; }
        header { display: flex; gap: 10px; }
        button { width: 120px; height: 40px; background: #0070f3; color: white; border: none; }
        a { display: inline-block; width: 80px; height: 30px; }
        input { width: 200px; height: 30px; }
    </style>
</head>
<body>
    <header>
        <nav>
            <button id="submit-btn">Run Pipeline</button>
            <a href="#docs" id="nav-link">Documentation</a>
        </nav>
        <input type="text" placeholder="Search..." id="search-input" />
    </header>
</body>
</html>"""

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        temp_path = f.name

    try:
        result = await verify_webcontainer_dom(temp_path, timeout_ms=5000)
        assert result["status"] == "PASSED", f"Expected PASSED, got: {result}"
        assert result["elements_verified"] >= 3
        assert result["horizontal_overflow"] is False
        assert len(result["console_errors"]) == 0
        assert result["latency_ms"] > 0
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_render_gate_failed_on_console_error():
    """Verify FAILED status when unhandled console errors are detected in preview."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <button style="width:100px;height:40px;">Button</button>
    <script>
        console.error("Critical rendering failure in ComponentX");
    </script>
</body>
</html>"""

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        temp_path = f.name

    try:
        result = await verify_webcontainer_dom(temp_path, timeout_ms=5000)
        assert result["status"] == "FAILED", f"Expected FAILED, got: {result}"
        assert len(result["console_errors"]) > 0
        assert any("ComponentX" in err for err in result["console_errors"])
        assert "Console/Page errors detected" in str(result.get("failure_reasons", []))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_render_gate_failed_on_uncaught_page_exception():
    """Verify FAILED status when uncaught JavaScript exceptions are thrown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <button style="width:100px;height:40px;">Button</button>
    <script>
        throw new Error("Uncaught crash: undefined is not a function");
    </script>
</body>
</html>"""

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        temp_path = f.name

    try:
        result = await verify_webcontainer_dom(temp_path, timeout_ms=5000)
        assert result["status"] == "FAILED", f"Expected FAILED, got: {result}"
        assert len(result["console_errors"]) > 0
        assert any("Uncaught crash" in err for err in result["console_errors"])
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_render_gate_failed_on_horizontal_overflow():
    """Verify FAILED status when DOM geometry exhibits horizontal scrollbar overflow."""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; }
        .runaway { width: 5000px; height: 100px; background: red; }
    </style>
</head>
<body>
    <button style="width:100px;height:40px;">Button</button>
    <div class="runaway">Overflowing wide element</div>
</body>
</html>"""

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        temp_path = f.name

    try:
        result = await verify_webcontainer_dom(temp_path, timeout_ms=5000)
        assert result["status"] == "FAILED", f"Expected FAILED, got: {result}"
        assert result["horizontal_overflow"] is True
        assert any("Horizontal overflow detected" in r for r in result.get("failure_reasons", []))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_render_gate_failed_on_zero_interactive_elements():
    """Verify FAILED status when preview renders zero interactive elements."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <p>Static text only with no buttons, anchors, inputs, or headers.</p>
</body>
</html>"""

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        temp_path = f.name

    try:
        result = await verify_webcontainer_dom(temp_path, timeout_ms=5000)
        assert result["status"] == "FAILED", f"Expected FAILED, got: {result}"
        assert result["elements_verified"] == 0
        assert any("No visible interactive elements" in r for r in result.get("failure_reasons", []))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_render_gate_unavailable_on_unreachable_preview():
    """Verify UNAVAILABLE status and descriptive error when preview port is down."""
    unreachable_url = "http://127.0.0.1:59998"
    result = await ui_visual_render_gate(preview_url=unreachable_url, timeout_ms=1500)

    assert result["status"] == "UNAVAILABLE"
    assert "error" in result
    assert "Preview unreachable" in result["error"]
    assert result["elements_verified"] == 0
    assert result["horizontal_overflow"] is False
    assert result["latency_ms"] > 0
