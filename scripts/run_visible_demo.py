import asyncio
import sys
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def run_visible_demo():
    print("[*] Launching visible Chrome browser on your desktop...")
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                slow_mo=200,
                args=["--start-maximized"]
            )
        except Exception:
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=200,
                args=["--start-maximized"]
            )

        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("[-->] Opening http://localhost:5173...")
        await page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(3000)

        print("[-->] Focusing chat input...")
        textarea = page.locator("textarea")
        await textarea.wait_for(state="visible", timeout=15000)
        await textarea.click()

        prompt_text = "Create a simple counter button component in React with Tailwind CSS"
        print(f"[-->] Typing prompt: '{prompt_text}'...")
        await textarea.type(prompt_text, delay=40)
        await page.wait_for_timeout(1000)

        print("[-->] Submitting prompt...")
        await textarea.press("Enter")

        print("[-->] Watching live response stream...")
        for _ in range(120):
            await page.wait_for_timeout(1000)
            if page.is_closed():
                break

        if not page.is_closed():
            await browser.close()
        print("[OK] Demo window closed.")

if __name__ == "__main__":
    asyncio.run(run_visible_demo())

