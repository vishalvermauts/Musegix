"""
Render Gate: Headless Playwright DOM layout and console verification gate for Musegix.
Verifies WebContainer preview DOM integrity, layout geometry, horizontal overflow,
interactive elements, and captures uncaught runtime/console errors.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright, Browser, Page


def _normalize_preview_url(url: str) -> str:
    """Ensure preview URL is properly formatted, supporting local file paths for testing."""
    stripped = url.strip()
    # Check if it looks like a local file path
    if (os.path.isabs(stripped) or os.path.exists(stripped)) and not (
        stripped.startswith("http://") or stripped.startswith("https://") or stripped.startswith("file://")
    ):
        return Path(stripped).resolve().as_uri()
    return stripped


async def verify_webcontainer_dom(
    preview_url: str = "http://localhost:5173",
    timeout_ms: int = 8000,
    viewport_width: int = 1280,
    viewport_height: int = 800,
) -> Dict[str, Any]:
    """
    Launches headless Chromium via Playwright to verify DOM integrity of the preview URL.

    Checks performed:
    1. Reachability: Verifies if the preview server is accessible.
    2. Console & Page Errors: Captures console errors and unhandled exceptions.
    3. Horizontal Overflow: Checks if document.documentElement.scrollWidth > window.innerWidth.
    4. Interactive Element Verification: Identifies and counts rendered interactive elements
       (button, a, input, nav, header) with non-zero dimensions.

    Returns:
        Dict with status ('PASSED', 'FAILED', or 'UNAVAILABLE'), metrics, and diagnostic details.
    """
    t0 = time.perf_counter()
    errors: List[str] = []
    target_url = _normalize_preview_url(preview_url)

    async with async_playwright() as p:
        browser: Optional[Browser] = None
        try:
            browser = await p.chromium.launch(headless=True)
            page: Page = await browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height}
            )

            # Listen for console errors
            page.on(
                "console",
                lambda msg: errors.append(f"[{msg.type.upper()}] {msg.text}")
                if msg.type == "error"
                else None,
            )

            # Listen for uncaught exceptions
            page.on("pageerror", lambda err: errors.append(f"[PAGEERROR] {str(err)}"))

            # Navigate to preview URL
            try:
                await page.goto(target_url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as e:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                return {
                    "status": "UNAVAILABLE",
                    "error": f"Preview unreachable: {str(e)}",
                    "preview_url": preview_url,
                    "elements_verified": 0,
                    "console_errors": errors[:5],
                    "horizontal_overflow": False,
                    "latency_ms": elapsed_ms,
                }

            # Check horizontal overflow (invariant: layout collisions occur when scrollWidth > innerWidth)
            has_overflow = await page.evaluate(
                "document.documentElement.scrollWidth > window.innerWidth"
            )

            # Check interactive element counts (must mount visible interactive elements)
            elements = await page.evaluate(
                """() => {
                    return [...document.querySelectorAll('button, a, input, nav, header')].map(e => {
                        const r = e.getBoundingClientRect();
                        return { tag: e.tagName.toLowerCase(), w: r.width, h: r.height };
                    }).filter(b => b.w > 0 && b.h > 0);
                }"""
            )

            failure_reasons = []
            if len(errors) > 0:
                failure_reasons.append(f"Console/Page errors detected ({len(errors)})")
            if has_overflow:
                failure_reasons.append(
                    "Horizontal overflow detected (scrollWidth > innerWidth)"
                )
            if len(elements) == 0:
                failure_reasons.append("No visible interactive elements mounted in DOM")

            passed = len(failure_reasons) == 0
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

            res = {
                "status": "PASSED" if passed else "FAILED",
                "elements_verified": len(elements),
                "console_errors": errors[:5],
                "horizontal_overflow": bool(has_overflow),
                "latency_ms": elapsed_ms,
                "preview_url": preview_url,
            }
            if not passed:
                res["failure_reasons"] = failure_reasons
            return res

        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


async def ui_visual_render_gate(
    preview_url: str = "http://localhost:5173",
    timeout_ms: int = 8000,
) -> Dict[str, Any]:
    """Alias for verify_webcontainer_dom matching FastMCP tool definition."""
    return await verify_webcontainer_dom(preview_url=preview_url, timeout_ms=timeout_ms)
