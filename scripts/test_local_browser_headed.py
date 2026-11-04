import asyncio
import sys
import time
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def run_headed_browser():
    print("=======================================================")
    print("[*] Launching visible browser on your local Windows PC...")
    print("=======================================================")
    
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                slow_mo=300,
                args=["--start-maximized"]
            )
            print("[OK] Launched local Google Chrome browser window.")
        except Exception as e:
            print(f"[INFO] Chrome channel fallback ({e}). Using Chromium...")
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=300,
                args=["--start-maximized"]
            )
            print("[OK] Launched local Chromium browser window.")

        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("[-->] Navigating to bolt.diy on http://localhost:5173...")
        await page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(3000)

        print("[-->] Locating chat prompt box...")
        textarea = page.locator("textarea")
        await textarea.wait_for(state="visible", timeout=15000)

        prompt_text = "Create a simple counter button component in React with Tailwind CSS"
        print(f"[-->] Typing prompt on screen: '{prompt_text}'...")
        await textarea.click()
        await textarea.type(prompt_text, delay=35)
        await page.wait_for_timeout(1000)

        print("[-->] Submitting prompt to Musegix Gateway...")
        await textarea.press("Enter")

        print("[-->] Watching live stream (Ysolveth ONNX router + Meta muse-spark-1.3)...")
        for i in range(20):
            await page.wait_for_timeout(1500)
            content = await page.content()
            if "Ysolveth" in content:
                print("[-->] LIVE: Ysolveth telemetry block visible on your screen!")
                break

        print("[-->] Waiting for Meta model code generation to complete...")
        await page.wait_for_timeout(15000)

        print("=======================================================")
        print("[OK] Generation complete! Leaving browser open for 15s...")
        print("=======================================================")
        await page.wait_for_timeout(15000)

        await browser.close()
        print("[OK] Local browser session closed.")

if __name__ == "__main__":
    asyncio.run(run_headed_browser())
