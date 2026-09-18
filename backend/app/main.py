from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import get_settings
from .database import SessionLocal, create_schema
from .models import ScanRun
from .services.scheduler import scheduler_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_schema()
    db = SessionLocal()
    try:
        for scan in db.query(ScanRun).filter(ScanRun.status.in_(["QUEUED", "RUNNING"])).all():
            scan.status = "INTERRUPTED"
            scan.error_message = "Proces aplikacji został przerwany"
            db.add(scan)
        db.commit()
    finally:
        db.close()
    scheduler = asyncio.create_task(scheduler_loop(), name="research-scheduler")
    yield
    scheduler.cancel()
    try:
        await scheduler
    except asyncio.CancelledError:
        pass


settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title="Allegro Product Hunter API",
    version="0.1.0",
    description="Local, evidence-first product research for Allegro.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
