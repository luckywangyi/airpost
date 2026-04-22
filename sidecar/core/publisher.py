"""Content publisher - automates posting to Xiaohongshu."""

import asyncio
import random
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from .browser import browser_manager

publisher_router = APIRouter()


class PublishRequest(BaseModel):
    account_id: str
    title: str
    body: str
    tags: list[str] = []
    image_paths: list[str] = []
    proxy: Optional[str] = None


class PublishResponse(BaseModel):
    success: bool
    message: str
    note_url: str = ""


async def _random_delay(min_s: float = 0.5, max_s: float = 2.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


@publisher_router.post("/post", response_model=PublishResponse)
async def publish_note(req: PublishRequest):
    """Publish a note to Xiaohongshu via browser automation."""
    try:
        ctx = await browser_manager.get_context(req.account_id, req.proxy)
        page = await ctx.new_page()

        await page.goto(
            "https://creator.xiaohongshu.com/publish/publish",
            wait_until="domcontentloaded",
        )
        await _random_delay(1, 3)

        # Upload images
        if req.image_paths:
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(req.image_paths)
                await _random_delay(2, 5)

        # Fill title
        title_input = await page.query_selector("#title")
        if title_input:
            await title_input.click()
            await _random_delay()
            await title_input.fill(req.title)
            await _random_delay()

        # Fill body
        body_input = await page.query_selector("#post-textarea")
        if not body_input:
            body_input = await page.query_selector('[contenteditable="true"]')
        if body_input:
            await body_input.click()
            await _random_delay()

            full_text = req.body
            if req.tags:
                tag_text = " ".join(f"#{t}" for t in req.tags)
                full_text += f"\n\n{tag_text}"

            await body_input.fill(full_text)
            await _random_delay(1, 2)

        # Click publish button
        publish_btn = await page.query_selector('button:has-text("发布")')
        if not publish_btn:
            publish_btn = await page.query_selector(".publishBtn")
        if publish_btn:
            await _random_delay(1, 3)
            await publish_btn.click()
            await _random_delay(3, 5)

        await browser_manager.save_cookies(req.account_id)

        current_url = page.url
        await page.close()

        return PublishResponse(
            success=True,
            message="发布成功",
            note_url=current_url,
        )
    except Exception as e:
        return PublishResponse(success=False, message=f"发布失败: {str(e)}")
