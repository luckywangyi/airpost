"""Task scheduler using APScheduler - supports smart pipeline scheduling."""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

scheduler_router = APIRouter()
_scheduler = AsyncIOScheduler()
logger = logging.getLogger("scheduler")


def start_scheduler():
    if not _scheduler.running:
        _scheduler.start()


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


class ScheduleTaskRequest(BaseModel):
    task_id: str
    task_type: str  # "publish" | "check_comments" | "collect_stats" | "pipeline" | "auto_reply"
    cron_expression: str  # "0 12 * * *" format
    params: dict = {}


class PipelineScheduleRequest(BaseModel):
    account_id: str
    niche: str = ""
    cron_expression: str = "0 10 * * *"  # default: daily at 10am
    auto_publish: bool = False
    auto_reply: bool = False
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    content_style: str = "种草推荐"
    content_tone: str = "活泼"
    max_daily_posts: int = 3


@scheduler_router.get("/jobs")
async def list_jobs():
    jobs = _scheduler.get_jobs()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in jobs
    ]


@scheduler_router.post("/add")
async def add_job(req: ScheduleTaskRequest):
    parts = req.cron_expression.split()
    if len(parts) != 5:
        return {"success": False, "message": "Invalid cron expression (need 5 parts)"}

    minute, hour, day, month, day_of_week = parts

    async def _task_runner():
        from .commenter import check_comments
        from .scraper import collect_stats

        if req.task_type == "check_comments":
            account_id = req.params.get("account_id", "")
            note_url = req.params.get("note_url", "")
            if account_id and note_url:
                await check_comments(account_id, note_url)
        elif req.task_type == "collect_stats":
            account_id = req.params.get("account_id", "")
            if account_id:
                await collect_stats(account_id)
        elif req.task_type == "pipeline":
            from .pipeline import run_pipeline, PipelineConfig
            config = PipelineConfig(**req.params)
            result = await run_pipeline(config)
            logger.info(f"Pipeline run: {result.message}")

    _scheduler.add_job(
        _task_runner,
        "cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        id=req.task_id,
        name=f"{req.task_type}_{req.task_id}",
        replace_existing=True,
    )
    return {"success": True, "message": f"Job {req.task_id} added"}


@scheduler_router.post("/pipeline")
async def schedule_pipeline(req: PipelineScheduleRequest):
    """One-click setup: schedule the full smart pipeline for an account."""
    parts = req.cron_expression.split()
    if len(parts) != 5:
        return {"success": False, "message": "Invalid cron expression"}

    minute, hour, day, month, day_of_week = parts
    job_id = f"pipeline_{req.account_id}"

    pipeline_params = {
        "account_id": req.account_id,
        "niche": req.niche,
        "auto_publish": req.auto_publish,
        "auto_reply": req.auto_reply,
        "api_key": req.api_key,
        "base_url": req.base_url,
        "model": req.model,
        "content_style": req.content_style,
        "content_tone": req.content_tone,
        "max_daily_posts": req.max_daily_posts,
    }

    async def _run():
        from .pipeline import run_pipeline, PipelineConfig
        config = PipelineConfig(**pipeline_params)
        result = await run_pipeline(config)
        logger.info(f"Scheduled pipeline: {result.message}")

    _scheduler.add_job(
        _run,
        "cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        id=job_id,
        name=f"智能管线_{req.account_id}",
        replace_existing=True,
    )

    # Also schedule comment checking every 4 hours if auto_reply is on
    if req.auto_reply:
        comment_job_id = f"comments_{req.account_id}"

        async def _check():
            from .pipeline import run_pipeline, PipelineConfig
            config = PipelineConfig(
                account_id=req.account_id,
                auto_reply=True,
                api_key=req.api_key,
                base_url=req.base_url,
                model=req.model,
            )
            # Only run comment stage
            logger.info(f"Auto comment check for {req.account_id}")

        _scheduler.add_job(
            _check,
            "cron",
            hour="*/4",
            id=comment_job_id,
            name=f"评论巡检_{req.account_id}",
            replace_existing=True,
        )

    return {
        "success": True,
        "message": f"智能管线已启动，cron: {req.cron_expression}",
        "job_id": job_id,
    }


@scheduler_router.delete("/remove/{task_id}")
async def remove_job(task_id: str):
    try:
        _scheduler.remove_job(task_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}
