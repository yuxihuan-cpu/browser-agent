"""Lightweight Playwright browser wrapper used by the flight booking agent."""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Dict, Optional

from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext, Page, async_playwright


class Browser:
    """Simple Chromium browser manager that keeps the window open for inspection."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._playwright = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self) -> Page:
        """Launch the browser and open a new page if not already running."""

        if self.page is not None:
            return self.page

        self._playwright = await async_playwright().start()
        headless = self._config.get("headless", False)
        launch_options: Dict[str, Any] = {"headless": headless}
        self._browser = await self._playwright.chromium.launch(**launch_options)

        context_options: Dict[str, Any] = {}
        if self._config.get("disable_security"):
            context_options["ignore_https_errors"] = True

        self._context = await self._browser.new_context(**context_options)
        self.page = await self._context.new_page()
        return self.page

    async def goto(self, url: str, **kwargs: Any) -> None:
        """Navigate to a URL, ensuring the browser is running first."""

        page = await self.start()
        await page.goto(url, **kwargs)

    async def close(self) -> None:
        """Close the Playwright resources."""

        if self.page:
            await self.page.close()
            self.page = None

        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def screenshot_base64(self) -> Optional[str]:
        """Return a base64 encoded screenshot of the current page."""

        if not self.page:
            return None

        image_bytes = await self.page.screenshot(full_page=True)
        return base64.b64encode(image_bytes).decode("utf-8")

    async def keep_alive(self) -> None:
        """Keep the browser window open until interrupted."""

        print("Browser will remain open. Press Ctrl+C to close.")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.close()
