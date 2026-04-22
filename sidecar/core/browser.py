"""Playwright browser manager - one context per account for cookie isolation."""

import json
import asyncio
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ACCOUNTS_DIR = DATA_DIR / "accounts"


class BrowserManager:
    _instance: Optional["BrowserManager"] = None
    _browser: Optional[Browser] = None
    _contexts: dict[str, BrowserContext] = {}

    @classmethod
    async def get_instance(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = BrowserManager()
        return cls._instance

    async def ensure_browser(self) -> Browser:
        if self._browser is None or not self._browser.is_connected():
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=False)
        return self._browser

    async def get_context(
        self,
        account_id: str,
        proxy: Optional[str] = None,
    ) -> BrowserContext:
        if account_id in self._contexts:
            return self._contexts[account_id]

        browser = await self.ensure_browser()
        ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
        storage_path = ACCOUNTS_DIR / f"{account_id}.json"

        ctx_opts: dict = {}
        if storage_path.exists():
            ctx_opts["storage_state"] = str(storage_path)
        if proxy:
            ctx_opts["proxy"] = {"server": proxy}

        context = await browser.new_context(**ctx_opts)
        self._contexts[account_id] = context
        return context

    async def save_cookies(self, account_id: str) -> None:
        ctx = self._contexts.get(account_id)
        if ctx:
            ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
            storage_path = ACCOUNTS_DIR / f"{account_id}.json"
            state = await ctx.storage_state()
            with open(storage_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

    async def close_context(self, account_id: str) -> None:
        ctx = self._contexts.pop(account_id, None)
        if ctx:
            await ctx.close()

    async def close_all(self) -> None:
        for ctx in self._contexts.values():
            await ctx.close()
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
            self._browser = None


browser_manager = BrowserManager()
