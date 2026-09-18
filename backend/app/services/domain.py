from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CandidateOffer:
    offer_id: str
    name: str
    seller_id: str
    seller_login: str | None
    price: float
    delivery_price: float | None
    currency: str
    url: str
    category_id: str | None = None
    category_name: str | None = None
    product_id: str | None = None
    ean: str | None = None
    model: str | None = None
    variant: str | None = None
    image_url: str | None = None
    carrier: str | None = None
    popularity: int | None = None
    popularity_range: str | None = None
    active: bool = True
    available: int | None = None
    seller_company: bool | None = None
    seller_super: bool | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    source_type: str = "ALLEGRO_API"
    observed_at: datetime | None = None
    identity_confidence: str = "LOW"
    ce_evidence: str | None = None
    generic_evidence: bool | None = None

    @property
    def total_price(self) -> float | None:
        if self.delivery_price is None:
            return None
        return round(self.price + self.delivery_price, 2)


@dataclass(slots=True)
class ProductGroup:
    key: str
    offers: list[CandidateOffer]
    identity_confidence: str
    identity_basis: str


@dataclass(slots=True)
class CheckOutcome:
    state: str  # PASS, FAIL, VERIFY
    code: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MarginBreakdown:
    sale_price: float
    purchase_price: float
    delivery: float
    commission: float
    other_fees: float
    taxes: float
    profit: float
    roi: float
