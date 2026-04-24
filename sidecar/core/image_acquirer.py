"""Multi-strategy image acquisition for automated publishing.

Priority chain:
  A. Local asset folder — random pick from user-configured directory
  B. Trending note covers — download from scraped Xiaohongshu notes
  C. Pexels API — free stock photos by keyword
  D. AI generation (DALL-E / compatible) — needs an image-capable API
  E. Picsum / Lorem Picsum — always-available free stock photo fallback
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Optional

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
IMAGE_CACHE_DIR = DATA_DIR / "image_cache"
USED_IMAGES_FILE = IMAGE_CACHE_DIR / "_used.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _load_used_set() -> set[str]:
    if USED_IMAGES_FILE.exists():
        try:
            return set(json.loads(USED_IMAGES_FILE.read_text("utf-8")))
        except Exception:
            pass
    return set()


def _save_used_set(used: set[str]):
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    USED_IMAGES_FILE.write_text(json.dumps(list(used), ensure_ascii=False), "utf-8")


def _mark_used(paths: list[str]):
    used = _load_used_set()
    used.update(paths)
    if len(used) > 5000:
        used = set(list(used)[-2000:])
    _save_used_set(used)


_KNOWN_IMAGE_CAPABLE_HOSTS = {"api.openai.com", "api.siliconflow.cn"}


async def acquire_images(
    topic: str,
    count: int = 1,
    asset_folder: str = "",
    pexels_api_key: str = "",
    ai_api_key: str = "",
    ai_base_url: str = "",
    ai_model: str = "",
    trending_image_urls: list[str] | None = None,
    account_id: str = "",
) -> list[str]:
    """Try strategies A->B->C->D->E to get `count` local image file paths."""

    results: list[str] = []

    # Strategy A: local asset folder
    if asset_folder:
        results = _pick_from_folder(asset_folder, topic, count)
        if results:
            logger.info(f"[ImageAcquirer] Strategy A (asset folder): got {len(results)} images")
            _mark_used(results)
            return results

    # Strategy B: download trending note covers
    if trending_image_urls:
        results = await _download_trending(trending_image_urls, count)
        if results:
            logger.info(f"[ImageAcquirer] Strategy B (trending covers): got {len(results)} images")
            return results

    # Strategy C: Pexels API
    if pexels_api_key:
        results = await _fetch_pexels(topic, pexels_api_key, count)
        if results:
            logger.info(f"[ImageAcquirer] Strategy C (Pexels): got {len(results)} images")
            return results

    # Strategy D: AI generation (DALL-E / compatible)
    if ai_api_key and _is_image_capable_api(ai_base_url):
        results = await _generate_ai_image(topic, ai_api_key, ai_base_url, count)
        if results:
            logger.info(f"[ImageAcquirer] Strategy D (AI generation): got {len(results)} images")
            return results
    elif ai_api_key:
        logger.info(f"[ImageAcquirer] Strategy D skipped: {ai_base_url} is not a known image-capable API")

    # Strategy E: free stock photos (Picsum + keyword-based Unsplash)
    results = await _fetch_free_stock(topic, count)
    if results:
        logger.info(f"[ImageAcquirer] Strategy E (free stock): got {len(results)} images")
        return results

    logger.warning("[ImageAcquirer] All strategies failed, no images acquired")
    return []


def _is_image_capable_api(base_url: str) -> bool:
    """Check if the API base URL is known to support image generation."""
    if not base_url:
        return True  # default OpenAI
    try:
        from urllib.parse import urlparse
        host = urlparse(base_url).hostname or ""
        return any(h in host for h in _KNOWN_IMAGE_CAPABLE_HOSTS)
    except Exception:
        return False


def _pick_from_folder(folder: str, topic: str, count: int) -> list[str]:
    """Pick up to `count` unused images from the asset folder."""
    folder_path = Path(folder)
    if not folder_path.is_dir():
        logger.warning(f"[ImageAcquirer] Asset folder not found: {folder}")
        return []

    used = _load_used_set()

    # Try topic-matching subfolder first
    topic_keywords = re.split(r'[，,、\s]+', topic)
    candidates: list[Path] = []
    for sub in folder_path.iterdir():
        if sub.is_dir() and any(kw in sub.name for kw in topic_keywords if kw):
            for f in sub.iterdir():
                if f.suffix.lower() in IMAGE_EXTENSIONS and str(f) not in used:
                    candidates.append(f)

    # Fall back to root folder
    if not candidates:
        for f in folder_path.rglob("*"):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS and str(f) not in used:
                candidates.append(f)

    if not candidates:
        return []

    random.shuffle(candidates)
    picked = candidates[:count]
    return [str(p) for p in picked]


async def _download_trending(urls: list[str], count: int) -> list[str]:
    """Download cover images from trending note URLs."""
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: list[str] = []

    valid_urls = [u for u in urls if u and u.startswith("http")][:count * 3]

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url in valid_urls:
            if len(results) >= count:
                break
            try:
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                ext = ".jpg"
                dest = IMAGE_CACHE_DIR / f"trending_{url_hash}{ext}"

                if dest.exists() and dest.stat().st_size > 1000:
                    results.append(str(dest))
                    continue

                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    content_type = resp.headers.get("content-type", "")
                    if "png" in content_type:
                        ext = ".png"
                    elif "webp" in content_type:
                        ext = ".webp"
                    dest = IMAGE_CACHE_DIR / f"trending_{url_hash}{ext}"
                    dest.write_bytes(resp.content)
                    results.append(str(dest))
            except Exception as e:
                logger.debug(f"[ImageAcquirer] Failed to download {url}: {e}")

    return results


async def _fetch_pexels(topic: str, api_key: str, count: int) -> list[str]:
    """Fetch stock photos from Pexels API."""
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: list[str] = []

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                "https://api.pexels.com/v1/search",
                params={"query": topic, "per_page": count * 2, "size": "medium"},
                headers={"Authorization": api_key},
            )
            if resp.status_code != 200:
                logger.warning(f"[ImageAcquirer] Pexels API returned {resp.status_code}")
                return []

            data = resp.json()
            photos = data.get("photos", [])

            for photo in photos[:count * 2]:
                if len(results) >= count:
                    break
                img_url = photo.get("src", {}).get("large", "")
                if not img_url:
                    continue
                try:
                    photo_id = photo.get("id", "unknown")
                    dest = IMAGE_CACHE_DIR / f"pexels_{photo_id}.jpg"
                    if dest.exists() and dest.stat().st_size > 1000:
                        results.append(str(dest))
                        continue
                    img_resp = await client.get(img_url)
                    if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                        dest.write_bytes(img_resp.content)
                        results.append(str(dest))
                except Exception as e:
                    logger.debug(f"[ImageAcquirer] Failed to download pexels photo: {e}")
        except Exception as e:
            logger.warning(f"[ImageAcquirer] Pexels API error: {e}")

    return results


async def _fetch_free_stock(topic: str, count: int) -> list[str]:
    """Fetch free stock photos from Picsum with keyword-seeded randomness."""
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: list[str] = []

    seed_base = hashlib.md5(topic.encode()).hexdigest()[:8]

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for i in range(count * 2):
            if len(results) >= count:
                break
            seed = f"{seed_base}_{i}_{random.randint(0, 9999)}"
            url = f"https://picsum.photos/seed/{seed}/1080/1440"
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    dest = IMAGE_CACHE_DIR / f"stock_{seed}.jpg"
                    dest.write_bytes(resp.content)
                    results.append(str(dest))
                    logger.debug(f"[ImageAcquirer] Picsum photo saved: {dest}")
            except Exception as e:
                logger.debug(f"[ImageAcquirer] Picsum fetch failed for seed {seed}: {e}")

    return results


async def _generate_ai_image(
    topic: str, api_key: str, base_url: str = "", count: int = 1
) -> list[str]:
    """Generate images via OpenAI DALL-E API."""
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: list[str] = []

    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None,
        )

        prompt = f"小红书风格精美配图，主题：{topic}。高质量、明亮、有吸引力的图片，适合社交媒体分享。"

        for i in range(count):
            try:
                response = await client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                    quality="standard",
                )
                if response.data and response.data[0].url:
                    img_url = response.data[0].url
                    async with httpx.AsyncClient(timeout=30) as http:
                        img_resp = await http.get(img_url)
                        if img_resp.status_code == 200:
                            url_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
                            dest = IMAGE_CACHE_DIR / f"ai_gen_{url_hash}.png"
                            dest.write_bytes(img_resp.content)
                            results.append(str(dest))
            except Exception as e:
                logger.warning(f"[ImageAcquirer] DALL-E generation {i+1} failed: {e}")
                if "model" in str(e).lower() or "not found" in str(e).lower():
                    break

    except Exception as e:
        logger.warning(f"[ImageAcquirer] AI image client init failed: {e}")

    return results
