"""Content publisher - automates posting to Xiaohongshu.

Key insights from open-source xhs-mcp projects:
- creator.xiaohongshu.com has multiple hidden tab elements with same text
  (opacity:1e-05, aria-hidden, tabindex=-1), must filter for visible ones.
- The ?target=image URL param may not work; need to explicitly click the tab.
- DOM selectors: .c-input_inner, .ql-editor, .css-k405vo (publish button)
"""

import asyncio
import logging
import os
import random
import traceback
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from .browser import browser_manager

logger = logging.getLogger(__name__)
publisher_router = APIRouter()

PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"


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
    """Publish an image note to Xiaohongshu via browser automation."""
    page = None
    try:
        logger.info(f"=== Publish request: title={req.title!r}, images={req.image_paths}")

        if not req.image_paths:
            return PublishResponse(success=False, message="小红书笔记必须包含至少一张图片")

        for img_path in req.image_paths:
            if not os.path.isfile(img_path):
                msg = f"图片文件不存在: {img_path}"
                logger.error(msg)
                return PublishResponse(success=False, message=msg)
            logger.info(f"  Image OK: {img_path} ({os.path.getsize(img_path)} bytes)")

        # Xiaohongshu title limit: 20 characters
        title = req.title
        if len(title) > 20:
            title = title[:19] + "…"
            logger.info(f"  Title truncated to 20 chars: {title!r}")

        ctx = await browser_manager.get_context(req.account_id, req.proxy)
        page = await ctx.new_page()

        # ── Step 1: Open publish page ──
        logger.info("Step 1: Opening publish page...")
        try:
            await page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as nav_err:
            logger.warning(f"  First navigation failed ({nav_err}), retrying with fresh context...")
            try:
                await page.close()
            except Exception:
                pass
            await browser_manager.close_context(req.account_id)
            ctx = await browser_manager.get_context(req.account_id, req.proxy)
            page = await ctx.new_page()
            await page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        current_url = page.url
        logger.info(f"  URL: {current_url}")

        if "login" in current_url or "passport" in current_url:
            logger.info("  Not logged in, trying SSO via main site...")
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            await page.goto(PUBLISH_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            current_url = page.url

        if "login" in current_url or "passport" in current_url:
            await page.close()
            return PublishResponse(
                success=False,
                message="创作者平台未登录，请先在账号管理中点击登录按钮重新登录",
            )

        # ── Step 2: Click the "上传图文" tab ──
        logger.info("Step 2: Switching to image upload tab...")

        # The page has multiple hidden tab elements with same text (opacity~0,
        # aria-hidden, tabindex=-1). We need to find and click the VISIBLE one.
        # Previous debug showed the tab text lives in <span class="title">.
        tab_clicked = False

        # Strategy 1: Find visible span with exact tab text and click it
        # (This was the first strategy to succeed in testing)
        try:
            result0 = await page.evaluate("""() => {
                const tabTexts = ['\u4e0a\u4f20\u89c6\u9891', '\u4e0a\u4f20\u56fe\u6587', '\u5199\u957f\u6587'];
                const allSpans = document.querySelectorAll('span');
                const tabSpans = [];
                allSpans.forEach(s => {
                    const t = s.textContent?.trim();
                    if (tabTexts.includes(t)) {
                        const rect = s.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            tabSpans.push({el: s, text: t, top: rect.top});
                        }
                    }
                });
                const target = tabSpans.find(s => s.text === '\u4e0a\u4f20\u56fe\u6587');
                if (target) {
                    target.el.click();
                    return {ok: true, method: 'direct-span'};
                }
                return {ok: false, found: tabSpans.length};
            }""")
            if result0.get('ok'):
                tab_clicked = True
                logger.info(f"  Tab clicked (direct-span): {result0}")
        except Exception as e:
            logger.warning(f"  Direct-span strategy failed: {e}")

        # Strategy 2: Playwright text-based click (with auto-retry and visibility)
        if not tab_clicked:
            for attempt in range(3):
                try:
                    await page.click('text=上传图文', timeout=5000)
                    tab_clicked = True
                    logger.info(f"  Clicked via page.click('text=上传图文') on attempt {attempt+1}")
                    break
                except Exception as e:
                    logger.warning(f"  page.click attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(2)

        # Strategy 3: Click the second tab-like element by index
        if not tab_clicked:
            logger.warning("  All text strategies failed, trying index-based click...")
            try:
                result2 = await page.evaluate("""() => {
                    // Find all visible top-level tab links/spans
                    const allSpans = document.querySelectorAll('span');
                    const tabTexts = ['上传视频', '上传图文', '写长文'];
                    const tabSpans = [];
                    allSpans.forEach(s => {
                        const t = s.textContent?.trim();
                        if (tabTexts.includes(t)) {
                            const rect = s.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                tabSpans.push({el: s, text: t, top: rect.top});
                            }
                        }
                    });
                    // Sort by vertical position, take the ones at same Y (tab row)
                    if (tabSpans.length >= 2) {
                        // Find the "上传图文" one
                        const target = tabSpans.find(s => s.text === '上传图文');
                        if (target) {
                            target.el.click();
                            return {ok: true, method: 'index-span'};
                        }
                    }
                    return {ok: false, found: tabSpans.length};
                }""")
                if result2.get('ok'):
                    tab_clicked = True
                    logger.info(f"  Index-based click succeeded: {result2}")
                else:
                    logger.warning(f"  Index-based click also failed: {result2}")
            except Exception as e:
                logger.warning(f"  Index-based strategy error: {e}")

        if not tab_clicked:
            logger.error("  FAILED to switch to image upload tab")

        await asyncio.sleep(3)

        # Record URL AFTER tab switch as the baseline for publish success detection
        pre_publish_url = page.url
        logger.info(f"  Pre-publish baseline URL: {pre_publish_url}")

        # Log current page state for debugging
        page_info = await page.evaluate("""() => {
            const inputs = document.querySelectorAll('input[type="file"]');
            const descriptions = [];
            inputs.forEach((inp, i) => {
                const rect = inp.getBoundingClientRect();
                descriptions.push({
                    index: i,
                    accept: inp.accept,
                    visible: rect.width > 0 && rect.height > 0,
                    width: rect.width,
                    height: rect.height
                });
            });
            return {
                url: location.href,
                title: document.title,
                fileInputs: descriptions,
                bodyText: document.body.innerText.substring(0, 500)
            };
        }""")
        logger.info(f"  Page state: url={page_info['url']}")
        logger.info(f"  File inputs found: {page_info['fileInputs']}")
        logger.info(f"  Page text preview: {page_info['bodyText'][:200]}")

        # ── Step 3: Upload images ──
        logger.info(f"Step 3: Uploading {len(req.image_paths)} images...")

        # The file input is typically hidden (0x0 px) behind a styled upload area.
        # Must use state='attached' instead of default 'visible'.
        file_input = None
        for sel in [
            'input[type="file"][accept*=".jpg"]',
            'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ]:
            try:
                file_input = await page.wait_for_selector(
                    sel, state='attached', timeout=8000
                )
                if file_input:
                    logger.info(f"  Found file input with: {sel}")
                    break
            except Exception:
                continue

        if not file_input:
            await page.close()
            return PublishResponse(
                success=False,
                message="找不到图片上传入口，页面可能未正确切换到图文标签。请确保账号已登录并重试。",
            )

        logger.info(f"  Found file input, uploading {req.image_paths}")
        await file_input.set_input_files(req.image_paths)

        # Wait for images to upload — check for thumbnail/preview elements
        total_size_mb = sum(os.path.getsize(p) for p in req.image_paths) / (1024 * 1024)
        base_wait = max(5, int(total_size_mb * 2))
        logger.info(f"  Total image size: {total_size_mb:.1f}MB, waiting {base_wait}s...")
        await asyncio.sleep(base_wait)

        # Verify images appeared on the page
        upload_check = await page.evaluate("""() => {
            // Look for image preview/thumbnail elements that appear after upload
            const indicators = document.querySelectorAll(
                '.upload-list-item, .image-item, [class*="upload"] img, ' +
                '[class*="preview"] img, [class*="cover"] img, ' +
                '.c-image img, img[src*="xhscdn"], img[src*="blob:"]'
            );
            return {count: indicators.length};
        }""")
        logger.info(f"  Upload indicators on page: {upload_check}")

        # ── Step 4: Fill title ──
        logger.info(f"Step 4: Filling title...")
        title_filled = False
        for sel in [
            '.c-input_inner input[type="text"]',
            '#title',
            'input[placeholder*="标题"]',
            'input[class*="title"]',
        ]:
            try:
                el = await page.wait_for_selector(sel, timeout=3000)
                if el:
                    await el.click()
                    await asyncio.sleep(0.2)
                    await el.fill("")
                    await el.type(title, delay=30)
                    title_filled = True
                    logger.info(f"  Title filled using selector: {sel}")
                    break
            except Exception:
                continue

        if not title_filled:
            # Try Playwright locator for placeholder text
            try:
                title_loc = page.get_by_placeholder("标题")
                if await title_loc.count() > 0:
                    await title_loc.first.fill(title)
                    title_filled = True
                    logger.info("  Title filled via placeholder locator")
            except Exception:
                pass

        if not title_filled:
            logger.warning("  Could not find title input")
        await _random_delay()

        # ── Step 5: Fill body + tags ──
        full_text = req.body
        if req.tags:
            tag_text = " ".join(f"#{t}" for t in req.tags)
            full_text += f"\n\n{tag_text}"

        logger.info(f"Step 5: Filling body ({len(full_text)} chars)...")
        body_filled = False
        for sel in ['.ql-editor', '#post-textarea', '[contenteditable="true"]']:
            try:
                el = await page.wait_for_selector(sel, timeout=3000)
                if el:
                    await el.click()
                    await asyncio.sleep(0.3)
                    await el.fill(full_text)
                    body_filled = True
                    logger.info(f"  Body filled using selector: {sel}")
                    break
            except Exception:
                continue

        if not body_filled:
            logger.warning("  Could not find body input")
        await _random_delay(1, 2)

        # ── Step 6: Click publish ──
        logger.info("Step 6: Publishing...")
        await _random_delay(1, 3)

        # Scroll to bottom first to make sure publish button is in viewport
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        # Dismiss any tippy/tooltip overlays that might intercept clicks
        await page.evaluate("""() => {
            document.querySelectorAll('[data-tippy-root], .tippy-box, .tippy-content').forEach(el => {
                el.remove();
            });
            document.body.click();
        }""")
        await asyncio.sleep(0.5)

        # Find the red "发布" submit button at the bottom of the page
        # Must distinguish from the sidebar "发布笔记" menu button
        publish_result = await page.evaluate(r"""() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent?.trim();
                // Exact match "发布" (not "发布笔记", "暂存离开", etc.)
                if (text === '\u53d1\u5e03') {
                    const rect = btn.getBoundingClientRect();
                    const style = window.getComputedStyle(btn);
                    // The submit button is typically red/primary colored and at the bottom
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            found: true,
                            disabled: btn.disabled,
                            rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                            bg: style.backgroundColor
                        };
                    }
                }
            }
            return {found: false};
        }""")
        logger.info(f"  Publish button state: {publish_result}")

        if not publish_result.get('found'):
            await page.close()
            return PublishResponse(success=False, message="找不到发布按钮")

        if publish_result.get('disabled'):
            # Check why it's disabled
            title_check = await page.evaluate("""() => {
                const titleInput = document.querySelector('.c-input_inner input[type="text"]');
                return titleInput ? titleInput.value.length : -1;
            }""")
            await page.close()
            return PublishResponse(
                success=False,
                message=f"发布按钮不可点击（标题长度: {title_check}），请检查标题是否超限或内容不完整",
            )

        # Click via JS to bypass any overlay issues
        logger.info("  Clicking publish button via JS...")
        await page.evaluate(r"""() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.textContent?.trim() === '\u53d1\u5e03' && !btn.disabled) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        btn.click();
                        return true;
                    }
                }
            }
            return false;
        }""")

        # Wait longer for the publish to complete (server-side processing)
        logger.info("  Waiting for publish result (10s)...")
        await asyncio.sleep(10)

        new_url = page.url
        await browser_manager.save_cookies(req.account_id)
        logger.info(f"  Post-publish URL: {new_url}")

        # Check for success/error signals on the page
        page_state = await page.evaluate("""() => {
            const body = document.body.innerText;
            const successKeywords = ['发布成功', '已发布', '审核中'];
            const errorKeywords = ['发布失败', '请重试', '内容违规'];
            const hasSuccess = successKeywords.some(k => body.includes(k));
            const hasError = errorKeywords.some(k => body.includes(k));

            // Check for toast/notification messages
            const toasts = document.querySelectorAll(
                '.toast, [class*="toast"], [class*="message"], [class*="notification"], [class*="alert"]'
            );
            let toastText = '';
            toasts.forEach(t => { toastText += t.textContent + ' '; });

            // Check if we're still on the publish form (title input still visible = not published)
            const stillOnForm = !!document.querySelector('.c-input_inner input[type="text"]');

            return {
                url: location.href,
                hasSuccess,
                hasError,
                toastText: toastText.trim().substring(0, 200),
                stillOnForm,
                bodySnippet: body.substring(0, 300)
            };
        }""")
        logger.info(f"  Page state after publish: {page_state}")

        url_changed = new_url != pre_publish_url
        navigated_away = (
            "publish/success" in new_url
            or "/explore/" in new_url
            or "publish/publish" not in new_url
        )

        if page_state.get('hasSuccess') or navigated_away:
            await page.close()
            logger.info(f"Published successfully: {new_url}")
            return PublishResponse(success=True, message="发布成功", note_url=new_url)

        if page_state.get('hasError'):
            await page.close()
            return PublishResponse(
                success=False,
                message=f"发布失败: {page_state.get('toastText', '未知错误')}",
            )

        # If we're no longer on the form, likely succeeded
        if url_changed and not page_state.get('stillOnForm'):
            await page.close()
            return PublishResponse(success=True, message="发布成功", note_url=new_url)

        # Uncertain — keep page open for user to check, return cautious message
        # Don't close the page so user can see what happened
        logger.warning("  Publish result uncertain, leaving browser open for user")
        return PublishResponse(
            success=False,
            message="发布结果不确定。请查看打开的浏览器窗口，确认是否需要手动完成发布。",
        )
    except Exception as e:
        logger.error(f"Publish failed: {e}\n{traceback.format_exc()}")
        if page:
            try:
                await page.close()
            except Exception:
                pass
        return PublishResponse(success=False, message=f"发布失败: {str(e)}")
