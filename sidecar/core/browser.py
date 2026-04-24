"""Playwright browser manager - one context per account for cookie isolation.

Supports both headed (for login/publish) and headless (for background tasks) modes.
"""

import json
import asyncio
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ACCOUNTS_DIR = DATA_DIR / "accounts"


def _storage_path(account_id: str) -> Path:
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    return ACCOUNTS_DIR / f"{account_id}.json"


class BrowserManager:
    _instance: Optional["BrowserManager"] = None
    _pw: Optional[Playwright] = None
    _headed_browser: Optional[Browser] = None
    _headless_browser: Optional[Browser] = None
    _contexts: dict[str, BrowserContext] = {}

    @classmethod
    async def get_instance(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = BrowserManager()
        return cls._instance

    async def _ensure_pw(self) -> Playwright:
        if self._pw is None:
            self._pw = await async_playwright().start()
        return self._pw

    async def _get_browser(self, headless: bool) -> Browser:
        if headless:
            if self._headless_browser is None or not self._headless_browser.is_connected():
                pw = await self._ensure_pw()
                self._headless_browser = await pw.chromium.launch(headless=True)
            return self._headless_browser
        else:
            if self._headed_browser is None or not self._headed_browser.is_connected():
                pw = await self._ensure_pw()
                self._headed_browser = await pw.chromium.launch(headless=False)
            return self._headed_browser

    async def get_context(
        self,
        account_id: str,
        proxy: Optional[str] = None,
        headless: bool = False,
    ) -> BrowserContext:
        """Get a persistent browser context for interactive operations (login, publish)."""
        if account_id in self._contexts:
            return self._contexts[account_id]

        browser = await self._get_browser(headless=headless)
        storage = _storage_path(account_id)

        ctx_opts: dict = {}
        if storage.exists():
            ctx_opts["storage_state"] = str(storage)
        if proxy:
            ctx_opts["proxy"] = {"server": proxy}

        context = await browser.new_context(**ctx_opts)
        self._contexts[account_id] = context
        return context

    async def get_temp_context(
        self,
        account_id: str,
        proxy: Optional[str] = None,
    ) -> BrowserContext:
        """Get a temporary headless context for background operations.

        Not cached — caller must close it when done.
        """
        browser = await self._get_browser(headless=True)
        storage = _storage_path(account_id)

        ctx_opts: dict = {}
        if storage.exists():
            ctx_opts["storage_state"] = str(storage)
        if proxy:
            ctx_opts["proxy"] = {"server": proxy}

        return await browser.new_context(**ctx_opts)

    async def save_cookies(self, account_id: str) -> None:
        ctx = self._contexts.get(account_id)
        if ctx:
            storage = _storage_path(account_id)
            state = await ctx.storage_state()
            with open(storage, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

    async def close_context(self, account_id: str) -> None:
        ctx = self._contexts.pop(account_id, None)
        if ctx:
            await ctx.close()

    async def close_all(self) -> None:
        for ctx in self._contexts.values():
            await ctx.close()
        self._contexts.clear()
        for b in (self._headed_browser, self._headless_browser):
            if b:
                await b.close()
        self._headed_browser = None
        self._headless_browser = None


browser_manager = BrowserManager()
