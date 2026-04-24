"""Content strategy engine - Explore/Evaluate/Exploit lifecycle for content directions."""

import json
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter

strategy_router = APIRouter()
logger = logging.getLogger("strategy")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
STRATEGY_DIR = DATA_DIR / "strategy"


class ContentDirection(BaseModel):
    id: str = ""
    name: str
    keywords: list[str] = []
    phase: str = "exploring"  # exploring | evaluating | exploiting | paused
    posts_count: int = 0
    avg_views: float = 0
    avg_engagement: float = 0
    direction_score: float = 0
    created_at: str = ""
    last_posted: str = ""


class AccountStrategy(BaseModel):
    account_id: str
    directions: list[ContentDirection] = []
    mode: str = "auto"  # explore | exploit | auto
    exploit_top_n: int = 2
    explore_posts_per_direction: int = 3
    min_data_posts: int = 3
    evaluation_hours: int = 48


class DirectionStats(BaseModel):
    direction_id: str
    direction_name: str
    matched_notes: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_collects: int = 0
    avg_engagement: float = 0
    direction_score: float = 0
    phase: str = "exploring"


class EvaluationResult(BaseModel):
    success: bool
    directions: list[DirectionStats] = []
    recommended_mode: str = ""
    message: str = ""


def _load_strategy(account_id: str) -> AccountStrategy:
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    path = STRATEGY_DIR / f"{account_id}_strategy.json"
    if not path.exists():
        return AccountStrategy(account_id=account_id)
    with open(path, "r", encoding="utf-8") as f:
        return AccountStrategy(**json.load(f))


def _save_strategy(strategy: AccountStrategy):
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    path = STRATEGY_DIR / f"{strategy.account_id}_strategy.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(strategy.model_dump(), f, ensure_ascii=False, indent=2)


def _match_note_to_direction(title: str, tags: list[str], direction: ContentDirection) -> bool:
    """Check if a note belongs to a direction by keyword matching."""
    text = (title + " " + " ".join(tags)).lower()
    name_lower = direction.name.lower()
    if name_lower in text:
        return True
    for kw in direction.keywords:
        if kw.lower() in text:
            return True
    return False


def _calc_direction_score(
    avg_engagement: float,
    total_interactions: int,
    posts_count: int,
    all_avg_engagement: float,
) -> float:
    """Weighted score: 50% relative engagement, 30% absolute volume, 20% consistency."""
    if posts_count == 0:
        return 0.0

    engagement_ratio = (avg_engagement / all_avg_engagement) if all_avg_engagement > 0 else 1.0
    engagement_score = min(engagement_ratio * 50, 100)

    avg_interactions = total_interactions / posts_count if posts_count > 0 else 0
    volume_score = min(avg_interactions / 10, 100) * 0.3

    consistency_score = min(posts_count / 5, 1.0) * 20

    return round(engagement_score + volume_score + consistency_score, 1)


def get_active_directions(strategy: AccountStrategy) -> list[ContentDirection]:
    """Decide which directions to generate content for based on current mode."""
    if not strategy.directions:
        return []

    active = [d for d in strategy.directions if d.phase != "paused"]
    if not active:
        return []

    mode = strategy.mode

    if mode == "explore":
        exploring = [d for d in active if d.posts_count < strategy.explore_posts_per_direction]
        return exploring if exploring else active

    if mode == "exploit":
        scored = sorted(active, key=lambda d: d.direction_score, reverse=True)
        return scored[: strategy.exploit_top_n]

    # auto mode
    exploring = [d for d in active if d.phase == "exploring"]
    if exploring:
        needs_posts = [d for d in exploring if d.posts_count < strategy.explore_posts_per_direction]
        if needs_posts:
            return needs_posts
        # All exploring directions have enough posts but haven't been evaluated yet
        return exploring

    exploiting = [d for d in active if d.phase == "exploiting"]
    if exploiting:
        return exploiting[: strategy.exploit_top_n]

    # Fallback: evaluated but not yet set to exploiting
    scored = sorted(active, key=lambda d: d.direction_score, reverse=True)
    return scored[: strategy.exploit_top_n]


def record_post(strategy: AccountStrategy, direction_id: str):
    """Increment post count for a direction after publishing."""
    for d in strategy.directions:
        if d.id == direction_id:
            d.posts_count += 1
            d.last_posted = datetime.now().isoformat()
            break
    _save_strategy(strategy)


# --- API Routes ---

@strategy_router.get("/get/{account_id}", response_model=AccountStrategy)
async def get_strategy(account_id: str):
    return _load_strategy(account_id)


@strategy_router.post("/save", response_model=AccountStrategy)
async def save_strategy(strategy: AccountStrategy):
    _save_strategy(strategy)
    return strategy


@strategy_router.post("/add_direction/{account_id}")
async def add_direction(account_id: str, name: str, keywords: str = ""):
    strategy = _load_strategy(account_id)
    direction = ContentDirection(
        id=uuid.uuid4().hex[:12],
        name=name,
        keywords=[k.strip() for k in keywords.split(",") if k.strip()] if keywords else [],
        created_at=datetime.now().isoformat(),
    )
    strategy.directions.append(direction)
    _save_strategy(strategy)
    return {"success": True, "direction": direction.model_dump()}


@strategy_router.post("/remove_direction/{account_id}")
async def remove_direction(account_id: str, direction_id: str):
    strategy = _load_strategy(account_id)
    strategy.directions = [d for d in strategy.directions if d.id != direction_id]
    _save_strategy(strategy)
    return {"success": True}


@strategy_router.post("/toggle_direction/{account_id}")
async def toggle_direction(account_id: str, direction_id: str):
    strategy = _load_strategy(account_id)
    for d in strategy.directions:
        if d.id == direction_id:
            d.phase = "paused" if d.phase != "paused" else "exploring"
            break
    _save_strategy(strategy)
    return {"success": True}


@strategy_router.post("/set_mode/{account_id}")
async def set_mode(account_id: str, mode: str):
    if mode not in ("explore", "exploit", "auto"):
        return {"success": False, "message": "无效模式"}
    strategy = _load_strategy(account_id)
    strategy.mode = mode
    _save_strategy(strategy)
    return {"success": True}


@strategy_router.post("/evaluate/{account_id}", response_model=EvaluationResult)
async def evaluate_directions(account_id: str):
    """Evaluate direction performance using historical note data."""
    strategy = _load_strategy(account_id)
    if not strategy.directions:
        return EvaluationResult(success=False, message="未配置内容方向")

    from .analyzer import _load_history
    notes = _load_history(account_id)
    if not notes:
        return EvaluationResult(success=False, message="暂无历史数据，请先采集数据")

    for n in notes:
        n.calc_engagement()

    all_avg_engagement = (
        sum(n.engagement_rate for n in notes) / len(notes) if notes else 0
    )

    results: list[DirectionStats] = []
    for direction in strategy.directions:
        if direction.phase == "paused":
            continue

        matched = [
            n for n in notes
            if _match_note_to_direction(n.title, n.tags, direction)
        ]

        if not matched:
            results.append(DirectionStats(
                direction_id=direction.id,
                direction_name=direction.name,
                phase=direction.phase,
            ))
            continue

        total_views = sum(n.views for n in matched)
        total_likes = sum(n.likes for n in matched)
        total_collects = sum(n.collects for n in matched)
        avg_eng = sum(n.engagement_rate for n in matched) / len(matched)
        total_interact = sum(
            n.likes + n.collects + n.comments + n.shares for n in matched
        )

        score = _calc_direction_score(
            avg_eng, total_interact, len(matched), all_avg_engagement
        )

        direction.avg_views = round(total_views / len(matched), 1)
        direction.avg_engagement = round(avg_eng, 2)
        direction.direction_score = score

        if len(matched) >= strategy.min_data_posts:
            if direction.phase == "exploring":
                direction.phase = "evaluating"

        results.append(DirectionStats(
            direction_id=direction.id,
            direction_name=direction.name,
            matched_notes=len(matched),
            total_views=total_views,
            total_likes=total_likes,
            total_collects=total_collects,
            avg_engagement=round(avg_eng, 2),
            direction_score=score,
            phase=direction.phase,
        ))

    # Auto-promote top directions to exploiting
    evaluating = [d for d in strategy.directions if d.phase == "evaluating"]
    if evaluating:
        evaluating_sorted = sorted(evaluating, key=lambda d: d.direction_score, reverse=True)
        for i, d in enumerate(evaluating_sorted):
            d.phase = "exploiting" if i < strategy.exploit_top_n else "paused"

    _save_strategy(strategy)

    recommended = "exploit" if all(
        d.phase in ("exploiting", "paused") for d in strategy.directions
    ) else "explore"

    return EvaluationResult(
        success=True,
        directions=sorted(results, key=lambda r: r.direction_score, reverse=True),
        recommended_mode=recommended,
        message=f"评估完成，分析了 {len(notes)} 条笔记",
    )
