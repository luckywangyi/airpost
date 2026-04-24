"""Comment manager - check and reply to comments."""

import asyncio
import random
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from .browser import browser_manager

commenter_router = APIRouter()


class Comment(BaseModel):
    user: str
    text: str
    time: str


class CommentCheckResponse(BaseModel):
    success: bool
    comments: list[Comment] = []
    message: str = ""


class ReplyRequest(BaseModel):
    account_id: str
    note_url: str
    comment_user: str
    reply_text: str
    proxy: Optional[str] = None


@commenter_router.post("/check", response_model=CommentCheckResponse)
async def check_comments(account_id: str, note_url: str):
    """Fetch comments from a note (runs headless)."""
    ctx = None
    try:
        ctx = await browser_manager.get_temp_context(account_id)
        page = await ctx.new_page()
        await page.goto(note_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        comments_data = await page.evaluate("""() => {
            const items = document.querySelectorAll('.comment-item, .note-comment');
            return Array.from(items).slice(0, 50).map(item => {
                const user = item.querySelector('.user-name, .name')?.textContent?.trim() || '';
                const text = item.querySelector('.content, .comment-text')?.textContent?.trim() || '';
                const time = item.querySelector('.time, .date')?.textContent?.trim() || '';
                return { user, text, time };
            });
        }""")

        await page.close()
        await ctx.close()
        return CommentCheckResponse(
            success=True,
            comments=[Comment(**c) for c in comments_data],
        )
    except Exception as e:
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass
        return CommentCheckResponse(success=False, message=str(e))


@commenter_router.post("/reply")
async def reply_comment(req: ReplyRequest):
    """Reply to a specific comment on a note (runs headless)."""
    ctx = None
    try:
        ctx = await browser_manager.get_temp_context(req.account_id, req.proxy)
        page = await ctx.new_page()
        await page.goto(req.note_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        replied = await page.evaluate(
            """(args) => {
            const [targetUser, replyText] = args;
            const items = document.querySelectorAll('.comment-item, .note-comment');
            for (const item of items) {
                const name = item.querySelector('.user-name, .name')?.textContent?.trim();
                if (name === targetUser) {
                    const replyBtn = item.querySelector('.reply-btn, button[class*="reply"]');
                    if (replyBtn) {
                        replyBtn.click();
                        return true;
                    }
                }
            }
            return false;
        }""",
            [req.comment_user, req.reply_text],
        )

        if replied:
            await asyncio.sleep(random.uniform(1, 2))
            reply_input = await page.query_selector(
                '.reply-input, textarea[placeholder*="回复"]'
            )
            if reply_input:
                await reply_input.fill(req.reply_text)
                await asyncio.sleep(random.uniform(0.5, 1.5))

                send_btn = await page.query_selector(
                    '.send-btn, button:has-text("发送")'
                )
                if send_btn:
                    await send_btn.click()
                    await asyncio.sleep(2)

        await page.close()
        await ctx.close()
        return {"success": replied, "message": "回复成功" if replied else "未找到目标评论"}
    except Exception as e:
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass
        return {"success": False, "message": str(e)}
