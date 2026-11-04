# Phase 4: FastMCP Tool Server & Real DOM Render Verification Gate

> **Status:** Queued (Follows Phase 3)  
> **Objective:** Expose developer intelligence tools over Model Context Protocol (MCP) and provide an honest headless browser verification gate that checks WebContainer DOM layout collisions and console errors.

---

## 1. FastMCP Server Specification (`mcp_servers/musegix_mcp.py`)

Tools exposed to `bolt.diy`:
1. `polyfabric_symbol_search(query: str)`: Searches indexed workspace symbols for targeted definitions.
2. `veylqora_memory_inspect(file_path: str)`: Reports anchored memory states (`ACTIVE`, `SUSPECTED_STALE`, `EVIDENCE_MISSING`).
3. `ui_visual_render_gate(preview_url: str)`: Runs headless Chromium via Playwright to verify DOM integrity.

---

## 2. Real Playwright DOM Verification Gate

Unlike canned mock responses, this launches headless Chromium, waits for the WebContainer preview to mount, and analyzes DOM geometry:

```python
import time
from playwright.async_api import async_playwright

async def verify_webcontainer_dom(preview_url: str) -> dict:
    t0 = time.perf_counter()
    errors = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        # Capture console errors
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        
        try:
            await page.goto(preview_url, wait_until="networkidle", timeout=8000)
        except Exception as e:
            await browser.close()
            return {"status": "UNAVAILABLE", "error": f"Preview unreachable: {str(e)}"}
            
        # Check horizontal overflow
        has_overflow = await page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        
        # Check interactive element counts
        elements = await page.evaluate("""() => {
            return [...document.querySelectorAll('button, a, input, nav, header')].map(e => {
                const r = e.getBoundingClientRect();
                return { tag: e.tagName, w: r.width, h: r.height };
            }).filter(b => b.w > 0 && b.h > 0);
        }""")
        
        await browser.close()

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    passed = len(errors) == 0 and not has_overflow and len(elements) > 0
    
    return {
        "status": "PASSED" if passed else "FAILED",
        "elements_verified": len(elements),
        "console_errors": errors[:5],
        "horizontal_overflow": has_overflow,
        "latency_ms": elapsed_ms
    }
```

---

## 3. Phase 4 Certification Gate Checklist

- [ ] **Gate 4.1:** FastMCP server responds cleanly to MCP protocol initialization.
- [ ] **Gate 4.2:** Playwright installs and runs in the cloud sandbox without missing OS libraries.
- [ ] **Gate 4.3:** `ui_visual_render_gate` correctly detects a deliberate runtime console error.
- [ ] **Gate 4.4:** `ui_visual_render_gate` returns `PASSED` on a clean, valid WebContainer preview.
- [ ] **Gate 4.5:** `bolt.diy` can invoke MCP tools over stdio during chat sessions.
