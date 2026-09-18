from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["PASS", "FAIL", "VERIFY"]


class ResearchSettings(BaseModel):
    min_demand: int = Field(default=30, ge=0)
    min_sellers: int = Field(default=2, ge=1)
    max_competition: int = Field(default=30, ge=1)
    min_profit: float = Field(default=20.0, ge=0)
    min_roi: float | None = Field(default=None, ge=0)
    commission_rate: float = Field(default=0.15, ge=0, le=1)
    other_fees: float = Field(default=0.0, ge=0)
    tax_rate: float = Field(default=0.0, ge=0, le=1)
    accepted_carriers: list[str] = Field(
        default_factory=lambda: ["InPost Paczkomat", "InPost Kurier", "DPD", "DHL", "DHL POP"]
    )
    require_ce_when_applicable: bool = True
    categories: list[str] = Field(default_factory=list)
    purchase_price_min: float | None = Field(default=None, ge=0)
    purchase_price_max: float | None = Field(default=None, ge=0)
    sale_price_min: float | None = Field(default=None, ge=0)
    sale_price_max: float | None = Field(default=None, ge=0)
    result_limit: int = Field(default=100, ge=1, le=1000)
    concurrency: int = Field(default=4, ge=1, le=10)
    requests_per_second: float = Field(default=2.0, gt=0, le=10)
    scheduler_interval: Literal["manual", "hourly", "6h", "12h", "daily"] = "manual"
    default_query: str = "organizery do domu"
    default_category_id: str = ""

    @field_validator("accepted_carriers")
    @classmethod
    def no_empty_carriers(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class AllegroSettingsUpdate(BaseModel):
    client_id: str = ""
    client_secret: str | None = None
    redirect_uri: str
    environment: Literal["production", "sandbox"] = "production"
    user_agent: str


class SettingsResponse(BaseModel):
    research: ResearchSettings
    allegro: dict[str, Any]


class ScanRequest(BaseModel):
    query: str | None = None
    category_id: str | None = None
    mode: Literal["live", "demo"] = "live"


class ScanResponse(BaseModel):
    id: int
    status: str
    pipeline_stage: str
    progress: int
    scanned_count: int
    pass_count: int
    fail_count: int
    verify_count: int
    new_count: int
    mode: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    scanned: int = 0
    passed: int = 0
    failed: int = 0
    verify: int = 0
    new_products: int = 0
    last_scan_at: datetime | None = None
    running_scan: ScanResponse | None = None


class ResultListItem(BaseModel):
    id: int
    product_id: int
    name: str
    image_url: str | None
    category: str | None
    allegro_product_id: str | None
    ean: str | None
    offer_count: int | None
    cheapest_price: float | None
    delivery_price: float | None
    carrier: str | None
    sale_price: float | None
    profit: float | None
    roi: float | None
    demand_sellers: list[dict[str, Any]]
    ce_status: str
    external: dict[str, Any]
    status: Status
    confidence: str
    is_watchlisted: bool
    is_new_opportunity: bool
    checked_at: datetime


class ResultsPage(BaseModel):
    items: list[ResultListItem]
    total: int
    limit: int
    offset: int


class ResultDetail(BaseModel):
    result: dict[str, Any]
    product: dict[str, Any]
    offers: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    external_competition: list[dict[str, Any]]
    history: list[dict[str, Any]]
    watchlisted: bool


class VerificationResolution(BaseModel):
    value: Any
    source_url: str
    confidence: Literal["HIGH", "MEDIUM"] = "HIGH"
    note: str | None = None


class ManualEvidenceRequest(BaseModel):
    field: Literal["identity", "shipping", "ce", "generic", "demand", "sale_price"]
    value: Any
    source_url: str
    confidence: Literal["HIGH", "MEDIUM"] = "HIGH"
    offer_id: int | None = None
