import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.scheduler import scheduler_router, start_scheduler, stop_scheduler
from core.account import account_router
from core.publisher import publisher_router
from core.commenter import commenter_router
from core.scraper import scraper_router
from ai.content_gen import ai_router

app = FastAPI(title="XHS Assistant Sidecar")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router, prefix="/account", tags=["account"])
app.include_router(publisher_router, prefix="/publish", tags=["publish"])
app.include_router(commenter_router, prefix="/comment", tags=["comment"])
app.include_router(scraper_router, prefix="/scraper", tags=["scraper"])
app.include_router(ai_router, prefix="/ai", tags=["ai"])
app.include_router(scheduler_router, prefix="/scheduler", tags=["scheduler"])


@app.on_event("startup")
async def on_startup():
    start_scheduler()


@app.on_event("shutdown")
async def on_shutdown():
    stop_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18765
    uvicorn.run(app, host="127.0.0.1", port=port)
