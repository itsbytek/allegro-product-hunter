from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import (
    Evidence,
    ExternalCompetition,
    Offer,
    PriceHistory,
    Product,
    ResearchResult,
    ScanRun,
    SystemLog,
    VerificationQueue,
    Watchlist,
)
from .schemas import (
    AllegroSettingsUpdate,
    DashboardStats,
    ManualEvidenceRequest,
    ResearchSettings,
    ResultDetail,
    ResultListItem,
    ResultsPage,
    ScanRequest,
    ScanResponse,
    SettingsResponse,
)
from .services.allegro import AllegroApiError, AllegroClient, ListingAccessDenied
from .services.settings_service import SettingsService
from .services.task_manager import scan_manager

router = APIRouter(prefix="/api")


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _offer_dict(offer: Offer) -> dict[str, Any]:
    return {
        "id": offer.id,
        "allegro_offer_id": offer.allegro_offer_id,
        "seller": offer.seller.login if offer.seller else None,
        "seller_id": offer.seller.allegro_seller_id if offer.seller else None,
        "price": offer.price,
        "delivery_price": offer.delivery_price,
        "total_price": offer.total_price,
        "carrier": offer.carrier,
        "popularity": offer.popularity,
        "demand_signal": offer.demand_signal,
        "active": offer.active,
        "available": offer.available,
        "url": offer.url,
        "identity_confidence": offer.identity_confidence,
        "checked_at": _dt(offer.checked_at),
    }


def _result_query(db: Session):
    latest = (
        db.query(
            ResearchResult.product_id,
            func.max(ResearchResult.checked_at).label("latest_at"),
        )
        .group_by(ResearchResult.product_id)
        .subquery()
    )
    return db.query(ResearchResult).join(
        latest,
        (ResearchResult.product_id == latest.c.product_id)
        & (ResearchResult.checked_at == latest.c.latest_at),
    )


def _list_item(db: Session, result: ResearchResult) -> ResultListItem:
    product = result.product
    external_rows = (
        db.query(ExternalCompetition).filter(ExternalCompetition.product_id == product.id).all()
    )
    watch = db.query(Watchlist).filter(Watchlist.product_id == product.id).one_or_none()
    cheapest = result.cheapest_offer
    return ResultListItem(
        id=result.id,
        product_id=product.id,
        name=product.name,
        image_url=product.image_url,
        category=product.category_name or product.category_id,
        allegro_product_id=product.allegro_product_id,
        ean=product.ean,
        offer_count=result.offer_count,
        cheapest_price=result.purchase_price,
        delivery_price=result.delivery_price,
        carrier=cheapest.carrier if cheapest else None,
        sale_price=result.realistic_sale_price,
        profit=result.profit,
        roi=result.roi,
        demand_sellers=result.demand_sellers or [],
        ce_status=result.ce_status,
        external={
            row.provider: {
                "price": row.price,
                "url": row.url,
                "risk": row.risk,
                "status": row.status,
            }
            for row in external_rows
        },
        status=result.status,  # type: ignore[arg-type]
        confidence=result.confidence,
        is_watchlisted=bool(watch and watch.enabled),
        is_new_opportunity=result.is_new_opportunity,
        checked_at=result.checked_at,
    )


def _filtered_results(
    db: Session,
    status: str | None,
    min_profit: float | None,
    min_roi: float | None,
    max_competition: int | None,
    sort: str,
    direction: str,
) -> list[ResearchResult]:
    query = _result_query(db)
    if status:
        query = query.filter(ResearchResult.status == status)
    if min_profit is not None:
        query = query.filter(ResearchResult.profit >= min_profit)
    if min_roi is not None:
        query = query.filter(ResearchResult.roi >= min_roi)
    if max_competition is not None:
        query = query.filter(ResearchResult.offer_count <= max_competition)
    if sort in {"demand", "popularity"}:
        rows = query.all()
        rows.sort(
            key=lambda row: sum(int(item.get("value") or 0) for item in (row.demand_sellers or [])),
            reverse=direction != "asc",
        )
        return rows
    columns = {
        "profit": ResearchResult.profit,
        "roi": ResearchResult.roi,
        "competition": ResearchResult.offer_count,
        "purchase_price": ResearchResult.purchase_price,
        "sale_price": ResearchResult.realistic_sale_price,
        "checked_at": ResearchResult.checked_at,
        "ranking": ResearchResult.ranking_score,
    }
    column = columns.get(sort, ResearchResult.ranking_score)
    query = query.order_by(
        column.asc().nullslast() if direction == "asc" else column.desc().nullslast()
    )
    return query.all()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@router.get("/settings", response_model=SettingsResponse)
def get_all_settings(db: Session = Depends(get_db)) -> SettingsResponse:
    service = SettingsService(db)
    return SettingsResponse(research=service.research(), allegro=service.allegro())


@router.put("/settings/research", response_model=ResearchSettings)
def update_research(settings: ResearchSettings, db: Session = Depends(get_db)) -> ResearchSettings:
    return SettingsService(db).save_research(settings)


@router.put("/settings/allegro")
def update_allegro(
    settings: AllegroSettingsUpdate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return SettingsService(db).save_allegro(settings)


@router.post("/allegro/test")
async def test_allegro(db: Session = Depends(get_db)) -> dict[str, Any]:
    service = SettingsService(db)
    client = AllegroClient(db, service.research().requests_per_second)
    try:
        await client.application_token(force=True)
        try:
            await client.listing(service.research().default_query, None, 1)
            listing_access = "GRANTED"
        except ListingAccessDenied:
            listing_access = "DENIED"
        return {"oauth": "OK", "listing_access": listing_access}
    except AllegroApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/allegro/oauth/url")
def oauth_url(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        return {"url": AllegroClient(db).authorization_url()}
    except AllegroApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/allegro/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(code: str, state: str, db: Session = Depends(get_db)) -> HTMLResponse:
    try:
        await AllegroClient(db).exchange_authorization_code(code, state)
    except AllegroApiError as exc:
        return HTMLResponse(f"<h1>Połączenie nieudane</h1><p>{str(exc)}</p>", status_code=400)
    frontend = get_settings().frontend_url
    return HTMLResponse(
        f"<h1>Allegro połączone</h1><p>Możesz zamknąć tę kartę.</p><script>setTimeout(()=>location.href='{frontend}/settings?oauth=success',700)</script>"
    )


@router.post("/scans", response_model=ScanResponse, status_code=202)
async def start_scan(request: ScanRequest, db: Session = Depends(get_db)) -> ScanRun:
    running = db.query(ScanRun).filter(ScanRun.status.in_(["QUEUED", "RUNNING"])).first()
    if running:
        raise HTTPException(status_code=409, detail=f"Skan {running.id} już trwa")
    defaults = SettingsService(db).research()
    scan = ScanRun(
        mode=request.mode,
        status="QUEUED",
        query=request.query or defaults.default_query,
        category_id=request.category_id or defaults.default_category_id or None,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    scan_manager.start(scan.id)
    return scan


@router.get("/scans/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int, db: Session = Depends(get_db)) -> ScanRun:
    scan = db.get(ScanRun, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Nie znaleziono skanu")
    return scan


@router.get("/scans", response_model=list[ScanResponse])
def list_scans(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return db.query(ScanRun).order_by(ScanRun.created_at.desc()).limit(limit).all()


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    last = db.query(ScanRun).order_by(ScanRun.created_at.desc()).first()
    running = (
        db.query(ScanRun)
        .filter(ScanRun.status.in_(["QUEUED", "RUNNING"]))
        .order_by(ScanRun.created_at.desc())
        .first()
    )
    if not last:
        return DashboardStats()
    return DashboardStats(
        scanned=last.scanned_count,
        passed=last.pass_count,
        failed=last.fail_count,
        verify=last.verify_count,
        new_products=last.new_count,
        last_scan_at=last.completed_at or last.created_at,
        running_scan=ScanResponse.model_validate(running) if running else None,
    )


@router.get("/results", response_model=ResultsPage)
def list_results(
    status: str | None = Query(None, pattern="^(PASS|FAIL|VERIFY)$"),
    min_profit: float | None = None,
    min_roi: float | None = None,
    max_competition: int | None = None,
    sort: str = "ranking",
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ResultsPage:
    rows = _filtered_results(db, status, min_profit, min_roi, max_competition, sort, direction)
    return ResultsPage(
        items=[_list_item(db, row) for row in rows[offset : offset + limit]],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


@router.get("/results/{result_id}", response_model=ResultDetail)
def result_detail(result_id: int, db: Session = Depends(get_db)) -> ResultDetail:
    result = db.get(ResearchResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Nie znaleziono wyniku")
    product = result.product
    offers = (
        db.query(Offer).filter(Offer.product_id == product.id).order_by(Offer.total_price).all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.product_id == product.id)
        .order_by(Evidence.observed_at.desc())
        .all()
    )
    external = (
        db.query(ExternalCompetition).filter(ExternalCompetition.product_id == product.id).all()
    )
    history = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product.id)
        .order_by(PriceHistory.captured_at)
        .all()
    )
    watch = db.query(Watchlist).filter(Watchlist.product_id == product.id).one_or_none()
    return ResultDetail(
        result={
            "id": result.id,
            "status": result.status,
            "confidence": result.confidence,
            "realistic_sale_price": result.realistic_sale_price,
            "realistic_price_method": result.realistic_price_method,
            "purchase_price": result.purchase_price,
            "delivery_price": result.delivery_price,
            "commission": result.commission,
            "other_fees": result.other_fees,
            "taxes": result.taxes,
            "profit": result.profit,
            "roi": result.roi,
            "offer_count": result.offer_count,
            "demand_sellers": result.demand_sellers,
            "ce_status": result.ce_status,
            "ce_source": result.ce_source,
            "passed_checks": result.passed_checks,
            "failed_checks": result.failed_checks,
            "verification_checks": result.verification_checks,
            "checked_at": _dt(result.checked_at),
        },
        product={
            "id": product.id,
            "name": product.name,
            "image_url": product.image_url,
            "category": product.category_name or product.category_id,
            "allegro_product_id": product.allegro_product_id,
            "ean": product.ean,
            "variant": product.variant,
            "parameters": product.parameters,
            "is_generic": product.is_generic,
        },
        offers=[_offer_dict(offer) for offer in offers],
        evidence=[
            {
                "id": row.id,
                "field": row.field,
                "value": row.value,
                "source_type": row.source_type,
                "source_id": row.source_id,
                "source_url": row.source_url,
                "confidence": row.confidence,
                "observed_at": _dt(row.observed_at),
            }
            for row in evidence
        ],
        external_competition=[
            {
                "provider": row.provider,
                "price": row.price,
                "url": row.url,
                "risk": row.risk,
                "status": row.status,
                "checked_at": _dt(row.checked_at),
            }
            for row in external
        ],
        history=[
            {
                "purchase_price": row.purchase_price,
                "sale_price": row.sale_price,
                "offer_count": row.offer_count,
                "profit": row.profit,
                "demand": row.demand,
                "captured_at": _dt(row.captured_at),
            }
            for row in history
        ],
        watchlisted=bool(watch and watch.enabled),
    )


@router.post("/products/{product_id}/watchlist")
def toggle_watchlist(product_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    if not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Nie znaleziono produktu")
    row = db.query(Watchlist).filter(Watchlist.product_id == product_id).one_or_none()
    if row is None:
        latest = (
            db.query(ResearchResult)
            .filter(ResearchResult.product_id == product_id)
            .order_by(ResearchResult.checked_at.desc())
            .first()
        )
        row = Watchlist(
            product_id=product_id, enabled=True, last_status=latest.status if latest else None
        )
    else:
        row.enabled = not row.enabled
    db.add(row)
    db.commit()
    return {"watchlisted": row.enabled}


@router.post("/products/{product_id}/evidence")
def add_manual_evidence(
    product_id: int, payload: ManualEvidenceRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Nie znaleziono produktu")
    offer = db.get(Offer, payload.offer_id) if payload.offer_id else None
    if payload.offer_id and (not offer or offer.product_id != product_id):
        raise HTTPException(status_code=400, detail="Oferta nie należy do produktu")
    if payload.field == "shipping" and offer:
        if isinstance(payload.value, dict):
            offer.carrier = payload.value.get("carrier")
            if payload.value.get("delivery_price") is not None:
                offer.delivery_price = float(payload.value["delivery_price"])
                offer.total_price = round(offer.price + offer.delivery_price, 2)
        else:
            offer.carrier = str(payload.value)
    elif payload.field == "generic":
        product.is_generic = bool(payload.value)
    elif payload.field == "identity" and isinstance(payload.value, dict):
        product.allegro_product_id = (
            payload.value.get("allegro_product_id") or product.allegro_product_id
        )
        product.ean = payload.value.get("ean") or product.ean
    elif payload.field == "demand" and offer:
        offer.popularity = int(payload.value)
        offer.demand_signal = "MANUAL_VERIFICATION"
    db.add(product)
    if offer:
        db.add(offer)
    evidence = Evidence(
        product_id=product_id,
        offer_id=offer.id if offer else None,
        field=payload.field,
        value=payload.value,
        source_type="MANUAL_VERIFICATION",
        source_url=payload.source_url,
        confidence=payload.confidence,
    )
    db.add(evidence)
    pending = (
        db.query(VerificationQueue)
        .filter(
            VerificationQueue.product_id == product_id,
            VerificationQueue.check_type == payload.field,
            VerificationQueue.status == "PENDING",
        )
        .all()
    )
    for item in pending:
        item.status = "RESOLVED"
        item.resolution = payload.model_dump(mode="json")
        item.resolved_at = datetime.now(UTC)
        db.add(item)
    db.commit()
    return {"saved": True, "note": "Dowód zostanie uwzględniony przy następnym skanie produktu"}


@router.get("/verification-queue")
def verification_queue(
    status: str = "PENDING", limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = (
        db.query(VerificationQueue)
        .filter(VerificationQueue.status == status)
        .order_by(VerificationQueue.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "product_id": row.product_id,
            "offer_id": row.offer_id,
            "check_type": row.check_type,
            "reason": row.reason,
            "source_url": row.source_url,
            "status": row.status,
            "created_at": _dt(row.created_at),
        }
        for row in rows
    ]


@router.get("/logs")
def logs(
    level: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = db.query(SystemLog)
    if level:
        query = query.filter(SystemLog.level == level.upper())
    rows = query.order_by(SystemLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "level": row.level,
            "event": row.event,
            "message": row.message,
            "scan_run_id": row.scan_run_id,
            "context": row.context,
            "created_at": _dt(row.created_at),
        }
        for row in rows
    ]


def _export_rows(db: Session, status: str | None) -> list[dict[str, Any]]:
    results = _filtered_results(db, status, None, None, None, "ranking", "desc")
    rows = []
    for result in results:
        item = _list_item(db, result)
        rows.append(
            {
                "status": item.status,
                "name": item.name,
                "category": item.category,
                "allegro_product_id": item.allegro_product_id,
                "ean": item.ean,
                "offer_count": item.offer_count,
                "purchase_price": item.cheapest_price,
                "delivery_price": item.delivery_price,
                "carrier": item.carrier,
                "sale_price": item.sale_price,
                "profit": item.profit,
                "roi": item.roi,
                "ce": item.ce_status,
                "confidence": item.confidence,
                "checked_at": item.checked_at.isoformat(),
            }
        )
    return rows


@router.get("/export/{format}")
def export_results(
    format: str,
    status: str | None = Query(None, pattern="^(PASS|FAIL|VERIFY)$"),
    db: Session = Depends(get_db),
):
    rows = _export_rows(db, status)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if format == "json":
        return Response(
            json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="allegro-hunter-{timestamp}.json"'
            },
        )
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else ["status"])
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            "\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="allegro-hunter-{timestamp}.csv"'
            },
        )
    if format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Wyniki"
        headers = list(rows[0].keys()) if rows else ["status"]
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(key) for key in headers])
        for column in sheet.columns:
            letter = column[0].column_letter
            sheet.column_dimensions[letter].width = min(
                45, max(12, max(len(str(cell.value or "")) for cell in column) + 2)
            )
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="allegro-hunter-{timestamp}.xlsx"'
            },
        )
    raise HTTPException(status_code=400, detail="Format musi być csv, xlsx lub json")
