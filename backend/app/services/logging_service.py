from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..models import SystemLog

logger = logging.getLogger("allegro_hunter")


def write_log(
    db: Session,
    level: str,
    event: str,
    message: str,
    scan_run_id: int | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    safe_context = {
        key: value
        for key, value in (context or {}).items()
        if all(secret not in key.casefold() for secret in ("token", "secret", "authorization"))
    }
    db.add(
        SystemLog(
            level=level.upper(),
            event=event,
            message=message,
            scan_run_id=scan_run_id,
            context=safe_context,
        )
    )
    db.commit()
    getattr(logger, level.casefold(), logger.info)("%s: %s", event, message)
