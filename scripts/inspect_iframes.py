import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://localhost:5173")
        await page.wait_for_timeout(3000)
        
        preview_btn = page.locator("button:has-text('Preview')")
        if await preview_btn.count() > 0:
            await preview_btn.first.click()
            await page.wait_for_timeout(3000)
            
        iframes = page.locator("iframe")
        count = await iframes.count()
        print(f"Total iframes: {count}")
        for i in range(count):
            src = await iframes.nth(i).get_attribute("src")
            print(f"iframe {i}: src={src}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
