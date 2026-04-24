"""Data scraper - collect note stats from Xiaohongshu creator center."""

import asyncio
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from .browser import browser_manager

logger = logging.getLogger(__name__)
scraper_router = APIRouter()

CREATOR_HOME_URL = "https://creator.xiaohongshu.com/"
NOTES_MGMT_URL = "https://creator.xiaohongshu.com/publish/note"
STATS_URL = "https://creator.xiaohongshu.com/statistics/notes"


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


def _parse_api_notes(api_responses: list[dict]) -> list[dict]:
    """Parse note data from intercepted XHR API responses."""
    results = []
    seen = set()

    for item in api_responses:
        data = item.get("data", {})
        if not isinstance(data, dict):
            continue

        # Try common response structures
        notes_list = (
            data.get("data", {}).get("notes", [])
            if isinstance(data.get("data"), dict) else
            data.get("notes", [])
        )
        if not notes_list and isinstance(data.get("data"), list):
            notes_list = data["data"]

        for note in notes_list:
            if not isinstance(note, dict):
                continue
            title = note.get("title", note.get("name", note.get("display_title", "")))
            if not title or title in seen:
                continue
            seen.add(title)

            note_id = note.get("note_id", note.get("id", ""))
            note_url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""

            interact = note.get("interact_info", note.get("stat", {}))
            if isinstance(interact, dict):
                views = interact.get("view_count", interact.get("views", 0))
                likes = interact.get("liked_count", interact.get("likes", 0))
                collects = interact.get("collected_count", interact.get("collects", 0))
                comments = interact.get("comment_count", interact.get("comments", 0))
                shares = interact.get("share_count", interact.get("shares", 0))
            else:
                views = likes = collects = comments = shares = 0

            results.append({
                "note_url": note_url,
                "title": title,
                "views": views or 0,
                "likes": likes or 0,
                "collects": collects or 0,
                "comments": comments or 0,
                "shares": shares or 0,
            })

    return results


@scraper_router.post("/collect_stats", response_model=ScrapeResponse)
async def collect_stats(account_id: str):
    """Collect stats for all notes of an account from creator center (runs headless)."""
    page = None
    try:
        ctx = await browser_manager.get_context(account_id)
        page = await ctx.new_page()

        # Intercept XHR responses to capture API data
        api_notes: list[dict] = []

        async def _on_response(response):
            url = response.url
            if any(kw in url for kw in ["/api/galaxy/creator/note", "/api/cas/note", "/note/list", "note_list"]):
                try:
                    body = await response.json()
                    logger.info(f"[Scraper] Intercepted API: {url[:100]} -> keys={list(body.keys()) if isinstance(body, dict) else 'list'}")
                    api_notes.append({"url": url, "data": body})
                except Exception:
                    pass

        page.on("response", _on_response)

        # Navigate to creator homepage (which works even when other pages are blocked)
        logger.info(f"[Scraper] Opening creator center for {account_id[:8]}...")
        await page.goto(CREATOR_HOME_URL, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)

        current_url = page.url
        logger.info(f"[Scraper] Creator home URL: {current_url}")

        if "login" in current_url or "passport" in current_url:
            logger.warning("[Scraper] Not logged in, trying SSO via main site...")
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            await page.goto(CREATOR_HOME_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            current_url = page.url

        if "login" in current_url or "passport" in current_url:
            await page.close()
            return ScrapeResponse(success=False, message="创作者平台未登录，请先在账号管理中重新登录")

        # Try notes management page first
        logger.info("[Scraper] Navigating to notes management...")
        await page.goto(NOTES_MGMT_URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(4)

        is_error_page = await page.evaluate("""() => {
            return !!document.querySelector('.error-page-container, .error-page-main');
        }""")

        if is_error_page:
            logger.warning("[Scraper] Notes management blocked, trying creator home for data...")
            # Go back to homepage and try to extract from there
            await page.goto(CREATOR_HOME_URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(4)

        # Log page state for debugging
        page_debug = await page.evaluate("""() => {
            const body = document.body.innerText;
            return {
                url: location.href,
                title: document.title,
                bodyLen: body.length,
                bodyPreview: body.substring(0, 500),
            };
        }""")
        logger.info(f"[Scraper] Page: {page_debug['url']}, title: {page_debug['title']}, body length: {page_debug['bodyLen']}")
        logger.info(f"[Scraper] Preview: {page_debug['bodyPreview'][:300]}")

        # Strategy: extract notes from the management page using multiple selector strategies
        notes_data = await page.evaluate(r"""() => {
            const results = [];
            const seen = new Set();

            // Helper: parse number from text like "1,234" or "1.2万"
            function parseNum(text) {
                if (!text) return 0;
                text = text.trim().replace(/,/g, '');
                if (text.includes('万')) return Math.round(parseFloat(text) * 10000);
                if (text.includes('亿')) return Math.round(parseFloat(text) * 100000000);
                const n = parseInt(text, 10);
                return isNaN(n) ? 0 : n;
            }

            // Strategy 1: Table rows (statistics page format)
            document.querySelectorAll('table tbody tr, .ant-table-row').forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 3) {
                    const titleEl = cells[0]?.querySelector('a, .title, span') || cells[0];
                    const title = titleEl?.textContent?.trim() || '';
                    if (!title || seen.has(title)) return;
                    seen.add(title);
                    const link = row.querySelector('a[href*="explore"], a[href*="note"]')?.href || '';
                    results.push({
                        note_url: link, title,
                        views: parseNum(cells[1]?.textContent),
                        likes: parseNum(cells[2]?.textContent),
                        collects: parseNum(cells[3]?.textContent),
                        comments: parseNum(cells[4]?.textContent),
                        shares: parseNum(cells[5]?.textContent),
                    });
                }
            });

            // Strategy 2: Card-like note items
            document.querySelectorAll(
                '[class*="note-item"], [class*="noteItem"], [class*="content-item"], ' +
                '[class*="note-card"], [class*="noteCard"]'
            ).forEach(card => {
                const titleEl = card.querySelector(
                    '[class*="title"], [class*="name"], h3, h4, .desc'
                );
                const title = titleEl?.textContent?.trim() || '';
                if (!title || seen.has(title)) return;
                seen.add(title);
                const link = card.querySelector('a')?.href || '';

                // Try to find stat numbers within the card
                const nums = [];
                card.querySelectorAll('[class*="count"], [class*="num"], [class*="data"], [class*="stat"]').forEach(el => {
                    nums.push(parseNum(el.textContent));
                });
                // If no stat-specific elements, try all small text/span with numbers
                if (nums.length === 0) {
                    card.querySelectorAll('span, em, .value').forEach(el => {
                        const n = parseNum(el.textContent);
                        if (n > 0) nums.push(n);
                    });
                }

                results.push({
                    note_url: link, title,
                    views: nums[0] || 0, likes: nums[1] || 0,
                    collects: nums[2] || 0, comments: nums[3] || 0,
                    shares: nums[4] || 0,
                });
            });

            // Strategy 3: Any list item containing a link to a note
            if (results.length === 0) {
                document.querySelectorAll('a[href*="/explore/"], a[href*="/note/"]').forEach(a => {
                    const title = a.textContent?.trim();
                    if (!title || title.length < 2 || title.length > 100 || seen.has(title)) return;
                    seen.add(title);
                    const container = a.closest('div, li, tr') || a.parentElement;
                    const nums = [];
                    if (container) {
                        container.querySelectorAll('span, em').forEach(el => {
                            const n = parseNum(el.textContent);
                            if (n > 0) nums.push(n);
                        });
                    }
                    results.push({
                        note_url: a.href, title,
                        views: nums[0] || 0, likes: nums[1] || 0,
                        collects: nums[2] || 0, comments: nums[3] || 0,
                        shares: 0,
                    });
                });
            }

            // Strategy 4: Broad search - find rows/divs that look like note entries
            if (results.length === 0) {
                const allDivs = document.querySelectorAll('div');
                allDivs.forEach(div => {
                    const rect = div.getBoundingClientRect();
                    // Look for horizontal strips that could be list items
                    if (rect.width < 300 || rect.height < 30 || rect.height > 200) return;
                    const imgs = div.querySelectorAll('img');
                    const texts = div.querySelectorAll('span, p, a');
                    if (imgs.length >= 1 && texts.length >= 2) {
                        const titleText = texts[0]?.textContent?.trim() || '';
                        if (!titleText || titleText.length < 2 || seen.has(titleText)) return;
                        seen.add(titleText);
                        const link = div.querySelector('a')?.href || '';
                        const nums = [];
                        texts.forEach(t => {
                            const n = parseNum(t.textContent);
                            if (n > 0) nums.push(n);
                        });
                        results.push({
                            note_url: link, title: titleText,
                            views: nums[0] || 0, likes: nums[1] || 0,
                            collects: nums[2] || 0, comments: 0, shares: 0,
                        });
                    }
                });
            }

            return { notes: results, debug: { strategies_tried: 4 } };
        }""")

        stats = notes_data.get("notes", [])
        logger.info(f"[Scraper] DOM extraction found {len(stats)} notes")

        # If DOM extraction failed, try to parse intercepted API responses
        if not stats and api_notes:
            logger.info(f"[Scraper] Trying to parse {len(api_notes)} intercepted API responses...")
            stats = _parse_api_notes(api_notes)
            logger.info(f"[Scraper] API extraction found {len(stats)} notes")

        # If still empty, try to extract summary stats from the homepage dashboard
        if not stats:
            homepage_stats = await page.evaluate(r"""() => {
                const results = [];
                const body = document.body.innerText;

                // Look for dashboard stat numbers on the homepage
                // XHS creator home often shows recent notes with basic metrics
                const allText = body;

                // Try to find note cards/items on the homepage
                document.querySelectorAll('div, section, li').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 200 || rect.height < 40 || rect.height > 300) return;

                    const text = el.innerText || '';
                    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
                    if (lines.length < 2) return;

                    // Check if this looks like a note entry (has a title-like line and numbers)
                    const hasNumbers = lines.some(l => /^\d/.test(l) || /[万亿]/.test(l));
                    const titleLine = lines.find(l => l.length >= 4 && l.length <= 50 && !/^\d/.test(l) && !/^[查看更多上传]/.test(l));

                    if (hasNumbers && titleLine) {
                        function parseNum(t) {
                            if (!t) return 0;
                            t = t.replace(/,/g, '');
                            if (t.includes('万')) return Math.round(parseFloat(t) * 10000);
                            const n = parseInt(t, 10);
                            return isNaN(n) ? 0 : n;
                        }
                        const numLines = lines.filter(l => /^\d/.test(l));
                        results.push({
                            note_url: '',
                            title: titleLine,
                            views: parseNum(numLines[0]),
                            likes: parseNum(numLines[1]),
                            collects: parseNum(numLines[2]),
                            comments: parseNum(numLines[3]),
                            shares: 0,
                        });
                    }
                });

                return results;
            }""")
            if homepage_stats:
                seen_titles = set()
                for s in homepage_stats:
                    if s["title"] not in seen_titles:
                        seen_titles.add(s["title"])
                        stats.append(s)
                logger.info(f"[Scraper] Homepage extraction found {len(stats)} notes")

        if not stats:
            dom_info = await page.evaluate("""() => {
                const tags = {};
                document.querySelectorAll('*').forEach(el => {
                    const cls = el.className;
                    if (typeof cls === 'string' && cls.length > 0 && cls.length < 100) {
                        const key = el.tagName + '.' + cls.split(' ')[0];
                        tags[key] = (tags[key] || 0) + 1;
                    }
                });
                return Object.entries(tags)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 30)
                    .map(([k, v]) => `${k}(${v})`);
            }""")
            logger.info(f"[Scraper] Page DOM classes: {dom_info}")

        await page.close()
        await browser_manager.save_cookies(account_id)

        if stats:
            msg = f"采集到 {len(stats)} 条笔记数据"
        elif is_error_page:
            msg = "创作者中心页面受限（可能是实名治理未完成），暂时无法采集数据。已发布的笔记数据会在管线发布时自动记录。"
        else:
            msg = "未找到笔记数据，可能是账号暂无已发布笔记"

        return ScrapeResponse(success=True, stats=[NoteStat(**n) for n in stats], message=msg)
    except Exception as e:
        logger.error(f"[Scraper] collect_stats failed: {e}")
        if page:
            try:
                await page.close()
            except Exception:
                pass
        return ScrapeResponse(success=False, message=str(e))


@scraper_router.post("/collect_single")
async def collect_single_note(account_id: str, note_url: str):
    """Collect stats for a single note (runs headless)."""
    ctx = None
    try:
        ctx = await browser_manager.get_temp_context(account_id)
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
        await ctx.close()
        return {
            "success": True,
            "stat": NoteStat(note_url=note_url, **data).model_dump(),
        }
    except Exception as e:
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass
        return {"success": False, "message": str(e)}
