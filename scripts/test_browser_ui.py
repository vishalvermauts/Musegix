import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path(r"C:\Users\mcmur\.gemini\antigravity\brain\151106c7-19fa-4a3b-ba8b-b722611f6452")

async def test_bolt_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        print("[1/5] Navigating to http://localhost:5173...")
        await page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        img_initial = ARTIFACT_DIR / "browser_test_01_initial.png"
        await page.screenshot(path=str(img_initial))
        print(f"Captured initial: {img_initial}")

        print("[2/5] Filling textarea with prompt...")
        textarea = page.locator("textarea")
        await textarea.wait_for(state="visible", timeout=10000)
        prompt = "Create a simple counter button component in React with Tailwind CSS"
        await textarea.fill(prompt)
        await page.wait_for_timeout(1000)

        img_typed = ARTIFACT_DIR / "browser_test_02_prompt_typed.png"
        await page.screenshot(path=str(img_typed))
        print(f"Captured typed: {img_typed}")

        print("[3/5] Submitting prompt via Enter...")
        await textarea.press("Enter")

        print("[4/5] Monitoring streaming generation and URL change...")
        for i in range(25):
            await page.wait_for_timeout(2000)
            url = page.url
            if "/chat/" in url:
                print(f"Chat session active at URL: {url} (step {i})")
            
            content = await page.content()
            if "Ysolveth" in content or "telemetry" in content:
                print(f"Detected Ysolveth in DOM at {i*2}s!")
                break
            if "Counter" in content or "boltArtifact" in content:
                print(f"Detected assistant output in DOM at {i*2}s!")
                break

        img_response = ARTIFACT_DIR / "browser_test_03_response.png"
        await page.screenshot(path=str(img_response))
        print(f"Captured response: {img_response}")

        # Let the model stream finish
        print("Waiting 10s for full response streaming...")
        await page.wait_for_timeout(10000)
        
        img_final = ARTIFACT_DIR / "browser_test_04_final.png"
        await page.screenshot(path=str(img_final))
        print(f"Captured final: {img_final}")

        await browser.close()
        print("[5/5] Browser test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_bolt_browser())
