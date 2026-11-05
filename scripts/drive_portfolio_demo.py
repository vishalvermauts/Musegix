import asyncio
import os
import sys
import time
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def build_portfolio():
    print("[*] Launching browser to drive bolt.diy live demo...")
    
    # We launch using channel='chrome' (visible headed window) or default chromium
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                slow_mo=150,
                args=["--start-maximized", "--no-first-run", "--no-default-browser-check"]
            )
            print("[+] Connected to local Google Chrome.")
        except Exception:
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=150,
                args=["--start-maximized", "--no-first-run", "--no-default-browser-check"]
            )
            print("[+] Connected to Chromium.")

        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("[1/5] Navigating to bolt.diy on http://localhost:5173...")
        await page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2500)

        # 1. Enable Full Access
        print("[2/5] Configuring 'Full Access' mode...")
        await page.evaluate("""() => {
            localStorage.setItem('tool_access_mode', 'full-access');
        }""")
        
        try:
            tool_btn = page.locator("button[aria-label*='Tool access'], button:has-text('Ask for all')")
            if await tool_btn.count() > 0:
                await tool_btn.first.click()
                await page.wait_for_timeout(500)
                full_access_item = page.locator("div[role='menuitem']:has-text('Full Access'), button:has-text('Full Access')")
                if await full_access_item.count() > 0:
                    await full_access_item.first.click()
                    print("      -> Selected 'Full Access' from dropdown.")
        except Exception as e:
            print(f"      -> Note on tool access: {e}")

        # 2. Focus and enter prompt
        print("[3/5] Entering prompt to build modern developer portfolio...")
        textarea = page.locator("textarea")
        await textarea.wait_for(state="visible", timeout=15000)
        await textarea.click()
        
        prompt = "Build a modern, sleek developer portfolio website with a Hero section, About Me, Project Showcase cards with filters, Skills badges, and a Contact form using React and Tailwind CSS."
        await textarea.type(prompt, delay=20)
        await page.wait_for_timeout(1000)

        # 3. Click the submit button or press Enter
        print("[4/5] Clicking Send / Submit button...")
        # Check for send button
        send_btn = page.locator("button[aria-label*='Send'], button:has(svg.i-ph\\\\:arrow-up), button:has(svg.i-ph\\\\:paper-plane-right)")
        if await send_btn.count() > 0 and await send_btn.first.is_visible():
            await send_btn.first.click()
        else:
            await textarea.press("Enter")

        print("[5/5] Request submitted! Streaming generation from Meta Muse model...")
        
        # Monitor progress and click Preview tab as soon as files are scaffolded
        preview_clicked = False
        start_time = time.time()
        while time.time() - start_time < 90:
            if page.is_closed():
                break
                
            page_text = await page.inner_text("body")
            if "Ysolveth Triage" in page_text:
                print("      ⚡ [Ysolveth Router] Triggered dynamically & routed to Meta Muse model.")
            
            # Check for Preview tab
            preview_btn = page.locator("button:has-text('Preview')")
            if await preview_btn.count() > 0:
                if await preview_btn.first.is_visible() and not preview_clicked:
                    await page.wait_for_timeout(4000)
                    try:
                        await preview_btn.first.click()
                        preview_clicked = True
                        print("      ✨ Workbench Preview opened!")
                    except Exception:
                        pass
            
            if preview_clicked:
                break
                
            await page.wait_for_timeout(2000)

        print("[+] Keeping browser open so you can interact with the portfolio...")
        # Keep open for 60 seconds
        await page.wait_for_timeout(60000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(build_portfolio())
