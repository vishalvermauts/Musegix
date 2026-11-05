import asyncio
import os
import sys
import time
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def test_kanban_preview():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://localhost:5173", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Set Full Access
        await page.evaluate("""() => {
            localStorage.setItem('tool_access_mode', 'full-access');
        }""")

        btn = page.locator("button:has-text('Create a Kanban board in react')")
        if await btn.count() > 0:
            print("Clicking 'Create a Kanban board in react'...")
            await btn.first.click()
        else:
            textarea = page.locator("textarea")
            await textarea.fill("Create a Kanban board in react")
            await textarea.press("Enter")

        print("Waiting for generation...")
        for i in range(30):
            await page.wait_for_timeout(3000)
            text = await page.inner_text("body")
            if "Preview" in text or "package.json" in text or "App.tsx" in text:
                print(f"[{i*3}s] Active generation detected in workbench...")
                
            preview_btn = page.locator("button:has-text('Preview')")
            if await preview_btn.count() > 0 and await preview_btn.first.is_visible():
                print("Clicking Preview tab...")
                await preview_btn.first.click()
                await page.wait_for_timeout(4000)
                break

        # Capture screenshot of the full workbench with preview
        await page.screenshot(path="test_kanban_workbench.png")
        print("Captured test_kanban_workbench.png")
        
        # Check frames inside page
        for idx, f in enumerate(page.frames):
            print(f"Frame {idx}: name={f.name}, url={f.url}")
            try:
                # If frame has elements, let's see its title or body
                body_elem = await f.locator("body").inner_text()
                print(f"   Body snippet: {body_elem[:100]}")
            except Exception as e:
                pass

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_kanban_preview())
