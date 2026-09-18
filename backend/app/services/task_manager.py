from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from ..database import SessionLocal
from ..models import ScanRun
from .allegro import AllegroApiError, AllegroClient, ListingAccessDenied
from .demo_data import demo_candidates
from .logging_service import write_log
from .pipeline import ResearchPipeline
from .settings_service import SettingsService


class ScanTaskManager:
    def __init__(self) -> None:
        self.tasks: dict[int, asyncio.Task[None]] = {}

    def start(self, scan_id: int) -> None:
        task = asyncio.create_task(self._execute(scan_id), name=f"scan-{scan_id}")
        self.tasks[scan_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(scan_id, None))

    async def _execute(self, scan_id: int) -> None:
        db = SessionLocal()
        try:
            scan = db.get(ScanRun, scan_id)
            if scan is None:
                return
            scan.status = "RUNNING"
            scan.pipeline_stage = "DISCOVER"
            scan.progress = 2
            scan.started_at = datetime.now(UTC)
            db.add(scan)
            db.commit()
            research_settings = SettingsService(db).research()
            if scan.mode == "demo":
                candidates = demo_candidates()
            else:
                client = AllegroClient(db, research_settings.requests_per_second)
                category_ids = (
                    [scan.category_id]
                    if scan.category_id
                    else (research_settings.categories or [None])
                )
                per_category = max(1, research_settings.result_limit // len(category_ids))
                discovered = []
                for category_id in category_ids:
                    discovered.extend(await client.listing(scan.query, category_id, per_category))
                candidates = list({offer.offer_id: offer for offer in discovered}.values())
            scan = db.get(ScanRun, scan_id)
            if scan is None:
                return
            await ResearchPipeline(db, research_settings).run(scan, candidates)
        except ListingAccessDenied as exc:
            scan = db.get(ScanRun, scan_id)
            if scan:
                scan.status = "COMPLETED_WITH_LIMITATION"
                scan.pipeline_stage = "DISCOVERY BLOCKED"
                scan.progress = 100
                scan.error_message = str(exc)
                scan.completed_at = datetime.now(UTC)
                db.add(scan)
                db.commit()
                write_log(
                    db,
                    "WARNING",
                    "LISTING_ACCESS_DENIED",
                    str(exc),
                    scan.id,
                    {"http_status": 403, "code": exc.code or "VerificationRequired"},
                )
        except AllegroApiError as exc:
            scan = db.get(ScanRun, scan_id)
            if scan:
                scan.status = "FAILED"
                scan.pipeline_stage = "DISCOVERY FAILED"
                scan.error_message = str(exc)
                scan.completed_at = datetime.now(UTC)
                db.add(scan)
                db.commit()
                write_log(
                    db,
                    "ERROR",
                    "ALLEGRO_API_ERROR",
                    str(exc),
                    scan.id,
                    {"http_status": exc.status_code, "code": exc.code},
                )
        except Exception as exc:
            scan = db.get(ScanRun, scan_id)
            if scan:
                scan.status = "FAILED"
                scan.pipeline_stage = "FAILED"
                scan.error_message = f"{type(exc).__name__}: {exc}"
                scan.completed_at = datetime.now(UTC)
                db.add(scan)
                db.commit()
                write_log(
                    db,
                    "ERROR",
                    "SCAN_FAILED",
                    f"Skan przerwany: {type(exc).__name__}",
                    scan.id,
                )
        finally:
            db.close()


scan_manager = ScanTaskManager()
