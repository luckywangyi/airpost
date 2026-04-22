"""Smart content analyzer - extract patterns from high-performing notes."""

import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter

analyzer_router = APIRouter()
DATA_DIR = Path(__file__).parent.parent.parent / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"


class NotePerformance(BaseModel):
    title: str
    views: int = 0
    likes: int = 0
    collects: int = 0
    comments: int = 0
    shares: int = 0
    engagement_rate: float = 0.0
    tags: list[str] = []
    word_count: int = 0
    has_emoji: bool = False
    title_length: int = 0

    def calc_engagement(self):
        total_interact = self.likes + self.collects + self.comments + self.shares
        if self.views > 0:
            self.engagement_rate = round(total_interact / self.views * 100, 2)
        return self


class ContentPattern(BaseModel):
    avg_title_length: float = 0
    avg_word_count: float = 0
    emoji_usage_rate: float = 0
    top_tags: list[str] = []
    best_engagement_rate: float = 0
    avg_engagement_rate: float = 0
    title_keywords: list[str] = []
    best_titles: list[str] = []
    best_post_hours: list[int] = []
    style_summary: str = ""


class AnalysisResult(BaseModel):
    success: bool
    pattern: Optional[ContentPattern] = None
    total_notes: int = 0
    high_performers: int = 0
    message: str = ""


def _load_history(account_id: str) -> list[NotePerformance]:
    """Load historical stats from local JSON store."""
    history_file = ANALYSIS_DIR / f"{account_id}_history.json"
    if not history_file.exists():
        return []
    with open(history_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [NotePerformance(**n).calc_engagement() for n in data]


def _save_history(account_id: str, notes: list[NotePerformance]):
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    history_file = ANALYSIS_DIR / f"{account_id}_history.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump([n.model_dump() for n in notes], f, ensure_ascii=False, indent=2)


def _extract_pattern(notes: list[NotePerformance]) -> ContentPattern:
    """Extract content patterns from a list of note performances."""
    if not notes:
        return ContentPattern()

    sorted_by_engagement = sorted(notes, key=lambda n: n.engagement_rate, reverse=True)
    top_20_pct = max(1, len(notes) // 5)
    high_performers = sorted_by_engagement[:top_20_pct]

    all_tags: dict[str, int] = {}
    for n in notes:
        for t in n.tags:
            all_tags[t] = all_tags.get(t, 0) + 1
    top_tags = sorted(all_tags, key=all_tags.get, reverse=True)[:10]

    title_words: dict[str, int] = {}
    for n in high_performers:
        chars = list(n.title.replace(" ", ""))
        for i in range(len(chars) - 1):
            bigram = chars[i] + chars[i + 1]
            if len(bigram.strip()) == 2:
                title_words[bigram] = title_words.get(bigram, 0) + 1
    title_keywords = sorted(title_words, key=title_words.get, reverse=True)[:15]

    return ContentPattern(
        avg_title_length=round(sum(n.title_length for n in high_performers) / len(high_performers), 1),
        avg_word_count=round(sum(n.word_count for n in high_performers) / len(high_performers), 0),
        emoji_usage_rate=round(sum(1 for n in high_performers if n.has_emoji) / len(high_performers) * 100, 1),
        top_tags=top_tags,
        best_engagement_rate=high_performers[0].engagement_rate if high_performers else 0,
        avg_engagement_rate=round(sum(n.engagement_rate for n in notes) / len(notes), 2),
        title_keywords=title_keywords,
        best_titles=[n.title for n in high_performers[:5]],
    )


@analyzer_router.post("/analyze", response_model=AnalysisResult)
async def analyze_account(account_id: str):
    """Analyze content performance for an account and extract patterns."""
    notes = _load_history(account_id)
    if not notes:
        return AnalysisResult(success=False, message="暂无历史数据，请先采集数据")

    for n in notes:
        n.calc_engagement()

    pattern = _extract_pattern(notes)
    high_count = sum(1 for n in notes if n.engagement_rate > pattern.avg_engagement_rate)

    return AnalysisResult(
        success=True,
        pattern=pattern,
        total_notes=len(notes),
        high_performers=high_count,
    )


@analyzer_router.post("/ingest_stats")
async def ingest_stats(account_id: str, stats: list[dict]):
    """Ingest scraped stats into history for analysis."""
    existing = _load_history(account_id)
    existing_titles = {n.title for n in existing}

    added = 0
    for s in stats:
        title = s.get("title", "")
        if not title or title in existing_titles:
            continue

        has_emoji = any(ord(c) > 0x1F300 for c in title)

        note = NotePerformance(
            title=title,
            views=s.get("views", 0),
            likes=s.get("likes", 0),
            collects=s.get("collects", 0),
            comments=s.get("comments", 0),
            shares=s.get("shares", 0),
            tags=s.get("tags", []),
            word_count=len(s.get("body", title)),
            has_emoji=has_emoji,
            title_length=len(title),
        ).calc_engagement()

        existing.append(note)
        existing_titles.add(title)
        added += 1

    _save_history(account_id, existing)
    return {"success": True, "added": added, "total": len(existing)}


@analyzer_router.get("/pattern/{account_id}")
async def get_pattern(account_id: str):
    """Get cached content pattern for prompt injection."""
    notes = _load_history(account_id)
    if not notes:
        return {"success": False, "pattern": None}
    for n in notes:
        n.calc_engagement()
    pattern = _extract_pattern(notes)
    return {"success": True, "pattern": pattern.model_dump()}
