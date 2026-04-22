"""Data scraper - collect note stats from Xiaohongshu."""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from .browser import browser_manager

scraper_router = APIRouter()


class NoteStat(BaseModel):
    note_url: str
    title: str
    views: int = 0
    likes: int = 0
    collects: int = 0
    comments: int = 0
    shares: int = 0


class ScrapeResponse(BaseModel):
    success: bool
    stats: list[NoteStat] = []
    message: str = ""


@scraper_router.post("/collect_stats", response_model=ScrapeResponse)
async def collect_stats(account_id: str):
    """Collect stats for all notes of an account from creator center."""
    try:
        ctx = await browser_manager.get_context(account_id)
        page = await ctx.new_page()

        await page.goto(
            "https://creator.xiaohongshu.com/statistics/notes",
            wait_until="domcontentloaded",
        )
        await asyncio.sleep(3)

        notes_data = await page.evaluate("""() => {
            const rows = document.querySelectorAll('.note-item, table tbody tr, .data-row');
            return Array.from(rows).map(row => {
                const title = row.querySelector('.title, .note-title, td:nth-child(1)')?.textContent?.trim() || '';
                const link = row.querySelector('a')?.href || '';

                const getText = (sel) => {
                    const el = row.querySelector(sel);
                    return parseInt(el?.textContent?.replace(/,/g, '') || '0', 10);
                };

                return {
                    note_url: link,
                    title: title,
                    views: getText('.views, td:nth-child(2)'),
                    likes: getText('.likes, td:nth-child(3)'),
                    collects: getText('.collects, td:nth-child(4)'),
                    comments: getText('.comments, td:nth-child(5)'),
                    shares: getText('.shares, td:nth-child(6)'),
                };
            });
        }""")

        await page.close()
        return ScrapeResponse(
            success=True,
            stats=[NoteStat(**n) for n in notes_data],
        )
    except Exception as e:
        return ScrapeResponse(success=False, message=str(e))


@scraper_router.post("/collect_single")
async def collect_single_note(account_id: str, note_url: str):
    """Collect stats for a single note."""
    try:
        ctx = await browser_manager.get_context(account_id)
        page = await ctx.new_page()
        await page.goto(note_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        data = await page.evaluate("""() => {
            const title = document.querySelector('.title, h1')?.textContent?.trim() || '';
            const getCount = (sel) => {
                const el = document.querySelector(sel);
                const text = el?.textContent?.replace(/[^0-9]/g, '') || '0';
                return parseInt(text, 10);
            };
            return {
                title,
                views: 0,
                likes: getCount('.like-count, [class*="like"] .count'),
                collects: getCount('.collect-count, [class*="collect"] .count'),
                comments: getCount('.comment-count, [class*="chat"] .count'),
                shares: getCount('.share-count, [class*="share"] .count'),
            };
        }""")

        await page.close()
        return {
            "success": True,
            "stat": NoteStat(note_url=note_url, **data).model_dump(),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
