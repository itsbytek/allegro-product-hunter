from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from ..database import SessionLocal
from ..models import ScanRun
from .settings_service import SettingsService
from .task_manager import scan_manager

INTERVALS = {
    "hourly": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "daily": timedelta(days=1),
}


async def scheduler_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            settings = SettingsService(db).research()
            interval = INTERVALS.get(settings.scheduler_interval)
            if interval:
                latest = (
                    db.query(ScanRun)
                    .filter(ScanRun.mode == "live")
                    .order_by(ScanRun.created_at.desc())
                    .first()
                )
                running = (
                    db.query(ScanRun).filter(ScanRun.status.in_(["QUEUED", "RUNNING"])).first()
                )
                if not running and (
                    latest is None
                    or latest.created_at.replace(tzinfo=UTC) + interval <= datetime.now(UTC)
                ):
                    scan = ScanRun(
                        mode="live",
                        status="QUEUED",
                        query=settings.default_query,
                        category_id=settings.default_category_id or None,
                    )
                    db.add(scan)
                    db.commit()
                    db.refresh(scan)
                    scan_manager.start(scan.id)
        finally:
            db.close()
        await asyncio.sleep(30)
