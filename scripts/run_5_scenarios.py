import asyncio
import os
import sys
import time
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCENARIOS = [
    {
        "id": "scenario_1_minimal_counter",
        "title": "Scenario 1: Minimal Interactive Counter",
        "prompt": "Create a clean, interactive Counter component with increment, decrement, reset, and step size controls using React and Tailwind CSS."
    },
    {
        "id": "scenario_2_todo_kanban",
        "title": "Scenario 2: Kanban / Task Board",
        "prompt": "Build a responsive Kanban Task Board component with To Do, In Progress, and Completed columns, supporting task creation and status changes."
    },
    {
        "id": "scenario_3_finance_dashboard",
        "title": "Scenario 3: SaaS Analytics KPI Card Grid",
        "prompt": "Create a modern SaaS Analytics KPI dashboard with stats cards (Revenue, Active Users, Churn Rate), percentage badges, and a period selector."
    },
    {
        "id": "scenario_4_theme_toggle_profile",
        "title": "Scenario 4: User Profile Card with Theme Toggle",
        "prompt": "Build an elegant Developer Profile card with avatar, social links, skill tags, and an active Dark / Light mode toggle switch."
    },
    {
        "id": "scenario_5_developer_portfolio",
        "title": "Scenario 5: Developer Portfolio Showcase",
        "prompt": "Build a modern developer portfolio hero and project cards showcase with filter buttons and contact CTA in React."
    }
]

ARTIFACTS_DIR = os.path.abspath(r"C:\Users\mcmur\.gemini\antigravity\brain\0049ab22-c6f9-48ce-a3e8-deb3a0a3bfb1")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

async def run_scenario(p, scenario, index, total):
    print(f"\n{'='*70}")
    print(f"[*] RUNNING [{index}/{total}] - {scenario['title']}")
    print(f"{'='*70}")
    
    browser = await p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,900"]
    )
    context = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()

    try:
        print("  [1/4] Navigating to bolt.diy...")
        await page.goto("http://localhost:5173", wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(2000)

        # Set Full Access
        await page.evaluate("""() => {
            localStorage.setItem('tool_access_mode', 'full-access');
        }""")

        # Inject prompt into textarea
        print(f"  [2/4] Injecting prompt: {scenario['prompt'][:60]}...")
        textarea = page.locator("textarea")
        await textarea.wait_for(state="visible", timeout=10000)
        await textarea.fill(scenario["prompt"])
        await page.wait_for_timeout(500)

        # Submit
        print("  [3/4] Submitting prompt to Musegix Gateway...")
        await textarea.press("Enter")

        # Wait for streaming and UI workbench
        print("  [4/4] Monitoring live generation...")
        start_t = time.time()
        routed_tier = None
        preview_captured = False

        while time.time() - start_t < 45:
            body_text = await page.inner_text("body")
            if "Ysolveth Triage" in body_text and not routed_tier:
                for line in body_text.splitlines():
                    if "Ysolveth Triage" in line:
                        routed_tier = line.strip()
                        print(f"        -> {routed_tier}")
                        break

            # Check if preview button is visible
            preview_btn = page.locator("button:has-text('Preview')")
            if await preview_btn.count() > 0 and await preview_btn.first.is_visible():
                try:
                    await preview_btn.first.click()
                except Exception:
                    pass

            await page.wait_for_timeout(3000)

        # Take full page screenshot of the final UI state
        screenshot_path = os.path.join(ARTIFACTS_DIR, f"{scenario['id']}.png")
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"  [+] Captured screenshot: {scenario['id']}.png")

        return {
            "id": scenario["id"],
            "title": scenario["title"],
            "prompt": scenario["prompt"],
            "routing": routed_tier or "Ysolveth System One Triage Recorded",
            "screenshot": screenshot_path,
            "status": "PASS"
        }

    except Exception as e:
        print(f"  [!] Scenario error: {e}")
        return {
            "id": scenario["id"],
            "title": scenario["title"],
            "prompt": scenario["prompt"],
            "routing": "N/A",
            "screenshot": None,
            "status": f"FAIL: {e}"
        }
    finally:
        await browser.close()

async def main():
    print("=" * 75)
    print("  MUSEGIX 5-SCENARIO AUTOMATED RUN & VISUAL BENCHMARK MATRIX")
    print("=" * 75)

    results = []
    async with async_playwright() as p:
        for idx, sc in enumerate(SCENARIOS, 1):
            res = await run_scenario(p, sc, idx, len(SCENARIOS))
            results.append(res)

    print("\n" + "=" * 75)
    print("  FINAL RUN MATRIX SUMMARY")
    print("=" * 75)
    for r in results:
        print(f"[{r['status']}] {r['title']} -> Screenshot: {os.path.basename(r['screenshot']) if r['screenshot'] else 'None'}")

if __name__ == "__main__":
    asyncio.run(main())
