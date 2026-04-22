"""Task scheduler using APScheduler."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter
from pydantic import BaseModel

scheduler_router = APIRouter()
_scheduler = AsyncIOScheduler()


def start_scheduler():
    if not _scheduler.running:
        _scheduler.start()


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


class ScheduleTaskRequest(BaseModel):
    task_id: str
    task_type: str  # "publish" | "check_comments" | "collect_stats"
    cron_expression: str  # "0 12 * * *" format
    params: dict = {}


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
        from .publisher import publish_note
        from .commenter import check_comments
        from .scraper import collect_stats
        from pydantic import BaseModel

        if req.task_type == "publish":
            pass
        elif req.task_type == "check_comments":
            account_id = req.params.get("account_id", "")
            note_url = req.params.get("note_url", "")
            if account_id and note_url:
                await check_comments(account_id, note_url)
        elif req.task_type == "collect_stats":
            account_id = req.params.get("account_id", "")
            if account_id:
                await collect_stats(account_id)

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


@scheduler_router.delete("/remove/{task_id}")
async def remove_job(task_id: str):
    try:
        _scheduler.remove_job(task_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}
