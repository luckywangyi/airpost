"""Account automation - login and status check."""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from .browser import browser_manager

account_router = APIRouter()


class LoginRequest(BaseModel):
    account_id: str
    proxy: Optional[str] = None


class LoginResponse(BaseModel):
    success: bool
    message: str
    nickname: str = ""


@account_router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Open Xiaohongshu creator login page for manual QR code scan.

    Logging in through the creator platform gives us cookies for both
    creator.xiaohongshu.com AND www.xiaohongshu.com at once.
    """
    try:
        # Close any existing context so we start fresh
        await browser_manager.close_context(req.account_id)
        ctx = await browser_manager.get_context(req.account_id, req.proxy)
        page = await ctx.new_page()

        # Login via creator platform — the QR scan here grants cookies for all subdomains
        await page.goto(
            "https://creator.xiaohongshu.com/login",
            wait_until="domcontentloaded",
        )

        # Wait for user to scan QR and be redirected away from the login page
        try:
            await page.wait_for_url(
                lambda url: "login" not in url and "passport" not in url,
                timeout=120_000,
            )
        except Exception:
            return LoginResponse(success=False, message="登录超时，请重试")

        await asyncio.sleep(2)
        await browser_manager.save_cookies(req.account_id)

        # Try to get nickname from the main site
        nickname = ""
        try:
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            el = await page.query_selector(".user-name")
            if el:
                nickname = await el.inner_text()
        except Exception:
            pass

        await browser_manager.save_cookies(req.account_id)
        await page.close()

        return LoginResponse(success=True, message="登录成功", nickname=nickname)
    except Exception as e:
        return LoginResponse(success=False, message=str(e))


@account_router.post("/check_status")
async def check_status(account_id: str):
    """Check if account session is still valid (runs headless)."""
    try:
        ctx = await browser_manager.get_temp_context(account_id)
        page = await ctx.new_page()
        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        is_logged_in = await page.evaluate("""() => {
            const selectors = [
                '.user-name',
                '.side-bar .user',
                '[class*="avatar"]',
                '[class*="user-info"]',
                '.reds-button-new[href*="user/profile"]',
                'a[href*="/user/profile/"]',
            ];
            if (selectors.some(s => document.querySelector(s))) return true;
            const loginBtn = document.querySelector('.login-btn')
                || document.querySelector('[class*="login"]');
            if (loginBtn && loginBtn.offsetParent !== null) return false;
            return !document.querySelector('.login-btn');
        }""")

        await page.close()
        await ctx.close()
        return {"valid": is_logged_in}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@account_router.post("/logout")
async def logout(account_id: str):
    """Close browser context for account."""
    await browser_manager.close_context(account_id)
    return {"success": True}
