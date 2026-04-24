"""Automated content pipeline - full end-to-end automation.

Pipeline flow:
  1. collect_stats  -> scrape performance data
  2. ingest_stats   -> feed data into analyzer
  3. explore_trends -> get current hot topics (headless)
  4. suggest_topics -> AI picks best topics (data-informed, per direction)
  5. generate       -> AI creates content (data-enriched prompt)
  6. acquire_images -> multi-strategy image acquisition
  7. auto_publish   -> push to Xiaohongshu
  8. (optional) check_comments -> monitor + auto-reply
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
    auto_publish: bool = True
    auto_reply: bool = False
    manual_review: bool = False
    reply_tone: str = "友好"
    content_style: str = "种草推荐"
    content_tone: str = "活泼"
    word_count: int = 300
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    max_daily_posts: int = 3
    asset_folder: str = ""
    pexels_api_key: str = ""
    strategy_mode: str = "auto"  # explore | exploit | auto
    content_directions: list[str] = []


class ContentItemResult(BaseModel):
    title: str = ""
    body: str = ""
    tags: list[str] = []
    score: int = 0
    status: str = "pending_review"
    message: str = ""
    image_paths: list[str] = []
    direction_id: str = ""
    direction_name: str = ""


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
    items: list[ContentItemResult] = []


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


def _sync_directions_from_config(config: PipelineConfig):
    """Sync user-configured directions into the strategy file (additive)."""
    if not config.content_directions:
        return
    from .strategy import _load_strategy, _save_strategy, ContentDirection
    import uuid as _uuid

    strategy = _load_strategy(config.account_id)
    strategy.mode = config.strategy_mode
    existing_names = {d.name for d in strategy.directions}

    for name in config.content_directions:
        name = name.strip()
        if name and name not in existing_names:
            strategy.directions.append(ContentDirection(
                id=_uuid.uuid4().hex[:12],
                name=name,
                created_at=datetime.now().isoformat(),
            ))
            existing_names.add(name)

    _save_strategy(strategy)


@pipeline_router.post("/run", response_model=PipelineRunResult)
async def run_pipeline(config: PipelineConfig):
    """Execute the full content pipeline for an account."""
    status = _get_status(config.account_id)
    if status.running:
        return PipelineRunResult(success=False, message="管线正在运行中")

    status.running = True
    status.stage = "starting"
    stages: list[str] = []
    result = PipelineRunResult(success=True)

    try:
        # Sync directions from frontend config
        _sync_directions_from_config(config)

        # Stage 1-2: Collect & analyze stats
        status.stage = "数据采集"
        try:
            from .scraper import collect_stats
            stats_resp = await collect_stats(config.account_id)
            if stats_resp.success and stats_resp.stats:
                stages.append("数据采集")
                status.stage = "数据分析"
                from .analyzer import ingest_stats
                stats_dicts = [s.model_dump() for s in stats_resp.stats]
                await ingest_stats(config.account_id, stats_dicts)
                stages.append("数据分析")
        except Exception as e:
            logger.warning(f"Stats collection failed: {e}")

        # Load strategy to determine which directions to generate for
        from .strategy import _load_strategy, get_active_directions, record_post

        strategy = _load_strategy(config.account_id)
        active_dirs = get_active_directions(strategy)
        use_directions = bool(active_dirs)

        # Stage 3: Explore trending (headless) — use first active direction or niche
        status.stage = "热点探索"
        trending_titles: list[str] = []
        trending_cover_urls: list[str] = []
        search_keyword = config.niche
        if use_directions and not search_keyword:
            search_keyword = active_dirs[0].name

        try:
            if search_keyword:
                from .hot_topics import explore_trending
                trending_resp = await explore_trending(config.account_id, search_keyword)
                if trending_resp.success:
                    trending_titles = [n.title for n in trending_resp.notes[:10]]
                    trending_cover_urls = [n.cover_url for n in trending_resp.notes if n.cover_url][:15]
                    stages.append("热点探索")
        except Exception as e:
            logger.warning(f"Trending exploration failed: {e}")

        # Stage 4 + 5: Topic suggestion + content generation (per direction)
        status.stage = "智能选题"
        generated_items: list[dict] = []

        if use_directions:
            posts_budget = config.max_daily_posts
            dirs_count = len(active_dirs)
            per_dir = max(1, posts_budget // dirs_count)

            for direction in active_dirs:
                if len(generated_items) >= config.max_daily_posts:
                    break

                dir_topics: list[str] = []
                try:
                    from ai.content_gen import suggest_topics, GenerateRequest
                    topic_req = GenerateRequest(
                        topic=direction.name,
                        account_id=config.account_id,
                        api_key=config.api_key,
                        base_url=config.base_url,
                        model=config.model,
                        trending_titles=trending_titles,
                        direction_name=direction.name,
                        direction_keywords=direction.keywords,
                    )
                    topic_resp = await suggest_topics(topic_req)
                    if topic_resp.success:
                        dir_topics = [s.topic for s in topic_resp.suggestions]
                        result.topics_suggested.extend(dir_topics)
                except Exception as e:
                    logger.warning(f"Topic suggestion failed for direction '{direction.name}': {e}")

                status.stage = "内容生成"
                gen_count = min(len(dir_topics), per_dir, config.max_daily_posts - len(generated_items))
                try:
                    from ai.content_gen import generate_content, GenerateRequest
                    for topic in dir_topics[:gen_count]:
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
                            direction_name=direction.name,
                            direction_keywords=direction.keywords,
                        )
                        gen_resp = await generate_content(gen_req)
                        if gen_resp.success:
                            generated_items.append({
                                "title": gen_resp.title,
                                "body": gen_resp.body,
                                "tags": gen_resp.tags,
                                "score": gen_resp.score,
                                "direction_id": direction.id,
                                "direction_name": direction.name,
                            })
                        await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f"Content generation failed for direction '{direction.name}': {e}")

            if result.topics_suggested:
                stages.append("智能选题")
        else:
            # Fallback: legacy single-niche mode
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
                topics: list[str] = []
                if topic_resp.success:
                    topics = [s.topic for s in topic_resp.suggestions]
                    result.topics_suggested = topics
                    stages.append("智能选题")

                status.stage = "内容生成"
                from ai.content_gen import generate_content
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
                            "direction_id": "",
                            "direction_name": "",
                        })
                    await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Content generation failed: {e}")

        result.content_generated = len(generated_items)
        if generated_items:
            stages.append("内容生成")
            PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
            queue_file = PIPELINE_DIR / f"{config.account_id}_queue.json"
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(generated_items, f, ensure_ascii=False, indent=2)

        # If manual_review is enabled, stop here and return items for review
        if config.manual_review and generated_items:
            for item in generated_items:
                result.items.append(ContentItemResult(
                    title=item["title"],
                    body=item["body"],
                    tags=item["tags"],
                    score=item["score"],
                    status="pending_review",
                    message="等待人工审核",
                    direction_id=item.get("direction_id", ""),
                    direction_name=item.get("direction_name", ""),
                ))
            result.stages_completed = stages
            result.message = f"管线完成内容生成（{len(generated_items)} 条），等待人工审核"
            return result

        # Stage 6+7: Acquire images & auto-publish (combined loop)
        score_threshold = 50 if strategy.mode == "explore" else 60

        if config.auto_publish and generated_items:
            from .image_acquirer import acquire_images
            from .publisher import publish_note, PublishRequest

            published = 0
            images_acquired = False

            for item in generated_items:
                item_result = ContentItemResult(
                    title=item["title"],
                    body=item["body"],
                    tags=item["tags"],
                    score=item["score"],
                    direction_id=item.get("direction_id", ""),
                    direction_name=item.get("direction_name", ""),
                )

                if item["score"] < score_threshold:
                    item_result.status = "failed"
                    item_result.message = f"评分过低 ({item['score']}分)，跳过发布"
                    result.items.append(item_result)
                    continue

                # Acquire images
                status.stage = "图片获取"
                image_paths: list[str] = []
                try:
                    image_paths = await acquire_images(
                        topic=item["title"],
                        count=3,
                        asset_folder=config.asset_folder,
                        pexels_api_key=config.pexels_api_key,
                        ai_api_key=config.api_key,
                        ai_base_url=config.base_url,
                        trending_image_urls=trending_cover_urls,
                        account_id=config.account_id,
                    )
                    item_result.image_paths = image_paths
                    if image_paths:
                        images_acquired = True
                except Exception as e:
                    logger.warning(f"Image acquisition failed for '{item['title']}': {e}")

                if not image_paths:
                    item_result.status = "failed"
                    item_result.message = "所有图片获取策略均失败"
                    result.items.append(item_result)
                    continue

                # Publish
                status.stage = "自动发布"
                try:
                    pub_req = PublishRequest(
                        account_id=config.account_id,
                        title=item["title"],
                        body=item["body"],
                        tags=item["tags"],
                        image_paths=image_paths,
                    )
                    pub_resp = await publish_note(pub_req)
                    item_result.status = "published" if pub_resp.success else "failed"
                    item_result.message = pub_resp.message
                    if pub_resp.success:
                        published += 1
                        if item.get("direction_id"):
                            record_post(strategy, item["direction_id"])
                except Exception as e:
                    logger.warning(f"Publish failed for '{item['title']}': {e}")
                    item_result.status = "failed"
                    item_result.message = str(e)

                result.items.append(item_result)
                await asyncio.sleep(10)

            if images_acquired:
                stages.append("图片获取")
            result.content_published = published
            if published > 0:
                stages.append("自动发布")

        elif generated_items and not config.auto_publish:
            for item in generated_items:
                result.items.append(ContentItemResult(
                    title=item["title"],
                    body=item["body"],
                    tags=item["tags"],
                    score=item["score"],
                    status="pending_review",
                    message="自动发布未启用",
                    direction_id=item.get("direction_id", ""),
                    direction_name=item.get("direction_name", ""),
                ))

        # Stage 8: Comments (stub)
        if config.auto_reply:
            status.stage = "评论管理"
            logger.info("Comment management stage is not yet implemented")

        result.stages_completed = stages
        pub_count = sum(1 for ir in result.items if ir.status == "published")
        fail_count = sum(1 for ir in result.items if ir.status == "failed")
        result.message = (
            f"管线完成，执行了 {len(stages)} 个阶段。"
            f"生成 {result.content_generated} 条内容，"
            f"发布成功 {pub_count} 条，失败 {fail_count} 条"
        )

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
