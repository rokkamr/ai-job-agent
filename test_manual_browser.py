import asyncio
import os
from app.automation.browser import BrowserManager

async def test_live_browser():
    print("\n🌐 Launching VISIBLE Chrome browser window...")
    # Pass headless=False to force visible browser window
    browser_mgr = BrowserManager(headless=False)
    
    try:
        page = await browser_mgr.get_page()
        test_url = "https://remoteok.com"
        print(f"👉 Navigating to test job site: {test_url}")
        await page.goto(test_url, timeout=30000, wait_until="domcontentloaded")
        
        print("✅ Page loaded successfully!")
        print("👀 Keeping browser tab open for 10 seconds so you can see it on your screen...")
        await asyncio.sleep(10)
        
    finally:
        await browser_mgr.close()
        print("🔒 Browser window closed.\n")

if __name__ == "__main__":
    asyncio.run(test_live_browser())
