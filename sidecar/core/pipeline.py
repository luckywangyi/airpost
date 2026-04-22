"""Automated content pipeline - connects all modules into a smart loop.

Pipeline flow:
  1. collect_stats  → scrape performance data
  2. ingest_stats   → feed data into analyzer
  3. explore_trends → get current hot topics
  4. suggest_topics → AI picks best topics (data-informed)
  5. generate       → AI creates content (data-enriched prompt)
  6. (optional) auto_publish → push to Xiaohongshu
  7. check_comments → monitor + auto-reply
  8. repeat
"""

import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

pipeline_router = APIRouter()
logger = logging.getLogger("pipeline")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PIPELINE_DIR = DATA_DIR / "pipeline"


class PipelineConfig(BaseModel):
    account_id: str
    niche: str = ""
    auto_publish: bool = False
    auto_reply: bool = False
    reply_tone: str = "友好"
    content_style: str = "种草推荐"
    content_tone: str = "活泼"
    word_count: int = 300
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    max_daily_posts: int = 3


class PipelineStatus(BaseModel):
    running: bool = False
    last_run: str = ""
    last_result: str = ""
    generated_count: int = 0
    published_count: int = 0
    stage: str = "idle"


class PipelineRunResult(BaseModel):
    success: bool
    stages_completed: list[str] = []
    topics_suggested: list[str] = []
    content_generated: int = 0
    content_published: int = 0
    comments_replied: int = 0
    message: str = ""


_pipeline_status: dict[str, PipelineStatus] = {}


def _get_status(account_id: str) -> PipelineStatus:
    if account_id not in _pipeline_status:
        _pipeline_status[account_id] = PipelineStatus()
    return _pipeline_status[account_id]


def _save_run_log(account_id: str, result: PipelineRunResult):
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    log_file = PIPELINE_DIR / f"{account_id}_runs.jsonl"
    entry = {
        "timestamp": datetime.now().isoformat(),
        **result.model_dump(),
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@pipeline_router.post("/run", response_model=PipelineRunResult)
async def run_pipeline(config: PipelineConfig):
    """Execute the full content pipeline for an account."""
    status = _get_status(config.account_id)
    if status.running:
        return PipelineRunResult(success=False, message="管线正在运行中")

    status.running = True
    status.stage = "starting"
    stages = []
    result = PipelineRunResult(success=True)

    try:
        # Stage 1: Collect stats
        status.stage = "数据采集"
        try:
            from .scraper import collect_stats
            stats_resp = await collect_stats(config.account_id)
            if stats_resp.success and stats_resp.stats:
                stages.append("数据采集")

                # Stage 2: Ingest into analyzer
                status.stage = "数据分析"
                from .analyzer import ingest_stats
                stats_dicts = [s.model_dump() for s in stats_resp.stats]
                await ingest_stats(config.account_id, stats_dicts)
                stages.append("数据分析")
        except Exception as e:
            logger.warning(f"Stats collection failed: {e}")

        # Stage 3: Explore trending
        status.stage = "热点探索"
        trending_titles = []
        try:
            if config.niche:
                from .hot_topics import explore_trending
                trending_resp = await explore_trending(config.account_id, config.niche)
                if trending_resp.success:
                    trending_titles = [n.title for n in trending_resp.notes[:10]]
                    stages.append("热点探索")
        except Exception as e:
            logger.warning(f"Trending exploration failed: {e}")

        # Stage 4: AI suggest topics
        status.stage = "智能选题"
        topics = []
        try:
            from ai.content_gen import suggest_topics, GenerateRequest
            topic_req = GenerateRequest(
                topic=config.niche or "综合",
                account_id=config.account_id,
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                trending_titles=trending_titles,
            )
            topic_resp = await suggest_topics(topic_req)
            if topic_resp.success:
                topics = [s.topic for s in topic_resp.suggestions]
                result.topics_suggested = topics
                stages.append("智能选题")
        except Exception as e:
            logger.warning(f"Topic suggestion failed: {e}")

        # Stage 5: Generate content for top topics
        status.stage = "内容生成"
        generated_items = []
        try:
            from ai.content_gen import generate_content, GenerateRequest
            gen_count = min(len(topics), config.max_daily_posts)
            for topic in topics[:gen_count]:
                gen_req = GenerateRequest(
                    topic=topic,
                    style=config.content_style,
                    tone=config.content_tone,
                    word_count=config.word_count,
                    account_id=config.account_id,
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.model,
                    trending_titles=trending_titles,
                )
                gen_resp = await generate_content(gen_req)
                if gen_resp.success:
                    generated_items.append({
                        "title": gen_resp.title,
                        "body": gen_resp.body,
                        "tags": gen_resp.tags,
                        "score": gen_resp.score,
                    })
                await asyncio.sleep(2)

            result.content_generated = len(generated_items)
            if generated_items:
                stages.append("内容生成")

                # Save generated content for review
                PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
                queue_file = PIPELINE_DIR / f"{config.account_id}_queue.json"
                with open(queue_file, "w", encoding="utf-8") as f:
                    json.dump(generated_items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Content generation failed: {e}")

        # Stage 6: Auto publish (if enabled and content scored high enough)
        if config.auto_publish and generated_items:
            status.stage = "自动发布"
            try:
                from .publisher import publish_note, PublishRequest
                published = 0
                for item in generated_items:
                    if item["score"] >= 75:
                        pub_req = PublishRequest(
                            account_id=config.account_id,
                            title=item["title"],
                            body=item["body"],
                            tags=item["tags"],
                        )
                        pub_resp = await publish_note(pub_req)
                        if pub_resp.success:
                            published += 1
                        await asyncio.sleep(10)

                result.content_published = published
                if published > 0:
                    stages.append("自动发布")
            except Exception as e:
                logger.warning(f"Auto publish failed: {e}")

        # Stage 7: Check and reply to comments (if enabled)
        if config.auto_reply:
            status.stage = "评论管理"
            try:
                from .commenter import check_comments
                from ai.content_gen import generate_reply

                # Check recent notes for new comments
                from .analyzer import _load_history
                notes = _load_history(config.account_id)
                replied = 0
                for note in notes[:5]:
                    if not hasattr(note, 'note_url'):
                        continue
                    # Simplified - in production would track replied comments
                await asyncio.sleep(1)
                result.comments_replied = replied
                if replied > 0:
                    stages.append("评论管理")
            except Exception as e:
                logger.warning(f"Comment management failed: {e}")

        result.stages_completed = stages
        result.message = f"管线完成，执行了 {len(stages)} 个阶段"

    except Exception as e:
        result.success = False
        result.message = f"管线执行失败: {str(e)}"
    finally:
        status.running = False
        status.stage = "idle"
        status.last_run = datetime.now().isoformat()
        status.last_result = result.message
        status.generated_count += result.content_generated
        status.published_count += result.content_published
        _save_run_log(config.account_id, result)

    return result


@pipeline_router.get("/status/{account_id}", response_model=PipelineStatus)
async def get_pipeline_status(account_id: str):
    return _get_status(account_id)


@pipeline_router.get("/queue/{account_id}")
async def get_content_queue(account_id: str):
    """Get generated content waiting for review/publish."""
    queue_file = PIPELINE_DIR / f"{account_id}_queue.json"
    if not queue_file.exists():
        return {"items": []}
    with open(queue_file, "r", encoding="utf-8") as f:
        items = json.load(f)
    return {"items": items}


@pipeline_router.get("/history/{account_id}")
async def get_run_history(account_id: str, limit: int = 20):
    """Get pipeline run history."""
    log_file = PIPELINE_DIR / f"{account_id}_runs.jsonl"
    if not log_file.exists():
        return {"runs": []}
    runs = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                runs.append(json.loads(line))
    return {"runs": runs[-limit:]}
