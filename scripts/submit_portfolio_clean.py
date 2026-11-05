import asyncio
import sys
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def submit_portfolio():
    print("[*] Launching browser to submit prompt directly...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--start-maximized", "--no-first-run", "--no-default-browser-check"]
        )
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("[1/3] Loading bolt.diy at http://localhost:5173...")
        await page.goto("http://localhost:5173", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Set tool access directly in localStorage
        await page.evaluate("""() => {
            localStorage.setItem('tool_access_mode', 'full-access');
        }""")

        prompt = "Build a modern, sleek developer portfolio website with a Hero section, About Me, Project Showcase cards with filters, Skills badges, and a Contact form using React and Tailwind CSS."
        print(f"[2/3] Setting prompt into textarea and dispatching input event...")

        # Directly set textarea value and trigger React change/input events
        await page.evaluate(f"""(text) => {{
            const ta = document.querySelector('textarea');
            if (ta) {{
                ta.focus();
                // Native value setter to trigger React's synthetic event system
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                nativeInputValueSetter.call(ta, text);
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""", prompt)

        await page.wait_for_timeout(1000)

        print("[3/3] Submitting via keyboard Enter...")
        # Focus textarea and press Enter
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

        # If still on home screen, try clicking the send button directly
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const sendBtn = btns.find(b => b.getAttribute('aria-label') === 'Send prompt' || b.querySelector('svg.i-ph\\\\:arrow-up') || b.querySelector('svg.i-ph\\\\:paper-plane-right'));
            if (sendBtn) {
                sendBtn.click();
            }
        }""")

        print("[+] Prompt submitted! Streaming project files from Meta Muse...")
        # Keep open for 45s while generating
        await page.wait_for_timeout(45000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(submit_portfolio())
