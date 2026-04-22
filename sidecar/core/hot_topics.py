"""Hot topics tracker - discover trending content on Xiaohongshu."""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from .browser import browser_manager

hot_topics_router = APIRouter()


class TrendingNote(BaseModel):
    title: str
    url: str = ""
    likes: int = 0
    author: str = ""


class TrendingResponse(BaseModel):
    success: bool
    notes: list[TrendingNote] = []
    message: str = ""


@hot_topics_router.post("/explore", response_model=TrendingResponse)
async def explore_trending(account_id: str, keyword: str = ""):
    """Scrape trending notes from Xiaohongshu explore/search page."""
    try:
        ctx = await browser_manager.get_context(account_id)
        page = await ctx.new_page()

        if keyword:
            url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
        else:
            url = "https://www.xiaohongshu.com/explore"

        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        # Scroll to load more
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(1)

        notes_data = await page.evaluate("""() => {
            const cards = document.querySelectorAll('.note-item, [class*="note-card"], .feeds-container section');
            return Array.from(cards).slice(0, 30).map(card => {
                const titleEl = card.querySelector('.title, h3, [class*="title"]');
                const linkEl = card.querySelector('a[href*="/explore/"], a[href*="/discovery/"]');
                const authorEl = card.querySelector('.author, .name, [class*="author"]');
                const likeEl = card.querySelector('.like-count, [class*="like"] span, .count');

                const likeText = likeEl?.textContent?.replace(/[^0-9.万k]/gi, '') || '0';
                let likes = 0;
                if (likeText.includes('万')) {
                    likes = Math.round(parseFloat(likeText) * 10000);
                } else if (likeText.toLowerCase().includes('k')) {
                    likes = Math.round(parseFloat(likeText) * 1000);
                } else {
                    likes = parseInt(likeText, 10) || 0;
                }

                return {
                    title: titleEl?.textContent?.trim() || '',
                    url: linkEl?.href || '',
                    author: authorEl?.textContent?.trim() || '',
                    likes: likes,
                };
            }).filter(n => n.title);
        }""")

        await page.close()

        notes = sorted(
            [TrendingNote(**n) for n in notes_data],
            key=lambda n: n.likes,
            reverse=True,
        )

        return TrendingResponse(success=True, notes=notes)
    except Exception as e:
        return TrendingResponse(success=False, message=str(e))


@hot_topics_router.post("/competitor", response_model=TrendingResponse)
async def analyze_competitor(account_id: str, competitor_url: str):
    """Scrape a competitor's profile to see their top performing content."""
    try:
        ctx = await browser_manager.get_context(account_id)
        page = await ctx.new_page()
        await page.goto(competitor_url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(1)

        notes_data = await page.evaluate("""() => {
            const cards = document.querySelectorAll('.note-item, [class*="note-card"], section.note');
            return Array.from(cards).slice(0, 20).map(card => {
                const titleEl = card.querySelector('.title, h3, [class*="title"]');
                const linkEl = card.querySelector('a');
                const likeEl = card.querySelector('.like-count, .count, [class*="like"] span');

                const likeText = likeEl?.textContent?.replace(/[^0-9.万k]/gi, '') || '0';
                let likes = 0;
                if (likeText.includes('万')) {
                    likes = Math.round(parseFloat(likeText) * 10000);
                } else if (likeText.toLowerCase().includes('k')) {
                    likes = Math.round(parseFloat(likeText) * 1000);
                } else {
                    likes = parseInt(likeText, 10) || 0;
                }

                return {
                    title: titleEl?.textContent?.trim() || '',
                    url: linkEl?.href || '',
                    likes: likes,
                };
            }).filter(n => n.title);
        }""")

        await page.close()

        notes = sorted(
            [TrendingNote(**n) for n in notes_data],
            key=lambda n: n.likes,
            reverse=True,
        )

        return TrendingResponse(success=True, notes=notes)
    except Exception as e:
        return TrendingResponse(success=False, message=str(e))
