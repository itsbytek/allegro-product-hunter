from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import VerificationQueue


class BrowserVerificationService:
    """Compliance boundary for public-page checks.

    Automatic browser extraction is deliberately not enabled. The service queues checks
    for a human and never attempts login, CAPTCHA solving, anti-bot bypass, or rate-limit bypass.
    """

    def __init__(self, db: Session):
        self.db = db

    def queue(
        self,
        check_type: str,
        reason: str,
        source_url: str | None,
        product_id: int | None = None,
        offer_id: int | None = None,
    ) -> VerificationQueue:
        existing = (
            self.db.query(VerificationQueue)
            .filter(
                VerificationQueue.product_id == product_id,
                VerificationQueue.offer_id == offer_id,
                VerificationQueue.check_type == check_type,
                VerificationQueue.status == "PENDING",
            )
            .first()
        )
        if existing:
            return existing
        row = VerificationQueue(
            product_id=product_id,
            offer_id=offer_id,
            check_type=check_type,
            reason=reason,
            source_url=source_url,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
