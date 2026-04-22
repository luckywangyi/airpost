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
    """Open Xiaohongshu login page for manual QR code scan."""
    try:
        ctx = await browser_manager.get_context(req.account_id, req.proxy)
        page = await ctx.new_page()
        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")

        # Wait for user to scan QR code and login (up to 120 seconds)
        try:
            await page.wait_for_url("**/explore**", timeout=120_000)
        except Exception:
            return LoginResponse(success=False, message="登录超时，请重试")

        await browser_manager.save_cookies(req.account_id)

        nickname = ""
        try:
            el = await page.query_selector(".user-name")
            if el:
                nickname = await el.inner_text()
        except Exception:
            pass

        return LoginResponse(success=True, message="登录成功", nickname=nickname)
    except Exception as e:
        return LoginResponse(success=False, message=str(e))


@account_router.post("/check_status")
async def check_status(account_id: str):
    """Check if account session is still valid."""
    try:
        ctx = await browser_manager.get_context(account_id)
        page = await ctx.new_page()
        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        is_logged_in = await page.evaluate("""() => {
            return document.querySelector('.user-name') !== null
                || document.querySelector('.side-bar .user') !== null;
        }""")

        await page.close()
        return {"valid": is_logged_in}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@account_router.post("/logout")
async def logout(account_id: str):
    """Close browser context for account."""
    await browser_manager.close_context(account_id)
    return {"success": True}
