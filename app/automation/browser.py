import asyncio
import os
from typing import Optional


class BrowserManager:
    def __init__(self, headless: bool = None):
        if headless is None:
            headless = os.getenv("HEADLESS", "true").lower() == "true"
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None

    async def start(self):
        if not self._browser:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
                )
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            except Exception as e:
                raise RuntimeError(f"Playwright browser automation not available in current environment: {e}")

    async def get_page(self) -> Page:
        if not self._context:
            await self.start()
        return await self._context.new_page()

    async def close(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._context = None
        self._playwright = None
