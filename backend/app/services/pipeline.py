from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    Evidence,
    ExternalCompetition,
    Offer,
    PriceHistory,
    Product,
    ProductMetric,
    ResearchResult,
    ScanRun,
    Seller,
    Watchlist,
)
from ..schemas import ResearchSettings
from .browser_verification import BrowserVerificationService
from .ce import validate_ce
from .competition import validate_competition
from .demand import validate_demand
from .domain import CandidateOffer, CheckOutcome, ProductGroup
from .external import ManualExternalProvider
from .final_validation import final_status, ranking_score
from .identity import group_products
from .logging_service import write_log
from .margin import calculate_margin, validate_margin
from .pricing import realistic_sale_price
from .shipping import find_cheapest, validate_shipping

PIPELINE_STAGES = [
    "DISCOVER",
    "GROUP PRODUCT",
    "VERIFY IDENTITY",
    "CHECK DEMAND",
    "CHECK COMPETITION",
    "FIND CHEAPEST SOURCE",
    "CHECK SHIPPING",
    "CHECK CE",
    "CALCULATE REALISTIC SELL PRICE",
    "CALCULATE PROFIT",
    "EXTERNAL COMPETITION",
    "FINAL VALIDATION",
]


class ResearchPipeline:
    def __init__(self, db: Session, settings: ResearchSettings):
        self.db = db
        self.settings = settings
        self.browser = BrowserVerificationService(db)

    def _update_scan(self, scan: ScanRun, stage: str, progress: int) -> None:
        scan.pipeline_stage = stage
        scan.progress = progress
        self.db.add(scan)
        self.db.commit()

    def _upsert_product(self, group: ProductGroup) -> tuple[Product, bool]:
        lead = group.offers[0]
        product: Product | None = None
        if lead.product_id:
            product = (
                self.db.query(Product)
                .filter(Product.allegro_product_id == lead.product_id)
                .one_or_none()
            )
        if product is None and lead.ean:
            product = self.db.query(Product).filter(Product.ean == lead.ean).first()
        if product is None:
            product = (
                self.db.query(Product)
                .filter(Product.name == lead.name, Product.category_id == lead.category_id)
                .first()
            )
        is_new = product is None
        if product is None:
            product = Product(name=lead.name)
        if lead.product_id:
            product.allegro_product_id = lead.product_id
        if lead.ean:
            product.ean = lead.ean
        product.name = lead.name
        product.category_id = lead.category_id
        product.category_name = lead.category_name
        product.variant = lead.variant
        product.image_url = lead.image_url
        product.parameters = lead.parameters
        if lead.generic_evidence is not None:
            product.is_generic = lead.generic_evidence
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product, is_new

    def _apply_manual_evidence(self, product: Product, group: ProductGroup) -> dict[str, Any]:
        rows = (
            self.db.query(Evidence)
            .filter(
                Evidence.product_id == product.id,
                Evidence.source_type == "MANUAL_VERIFICATION",
            )
            .order_by(Evidence.observed_at)
            .all()
        )
        latest: dict[str, Any] = {}
        stored_offers = {
            offer.id: offer
            for offer in self.db.query(Offer).filter(Offer.product_id == product.id).all()
        }
        candidates = {offer.offer_id: offer for offer in group.offers}
        for row in rows:
            latest[row.field] = row.value
            stored = stored_offers.get(row.offer_id) if row.offer_id else None
            candidate = candidates.get(stored.allegro_offer_id) if stored else None
            if candidate and row.field == "shipping":
                value = row.value if isinstance(row.value, dict) else {"carrier": row.value}
                candidate.carrier = value.get("carrier") or candidate.carrier
                if value.get("delivery_price") is not None:
                    candidate.delivery_price = float(value["delivery_price"])
            if candidate and row.field == "demand":
                candidate.popularity = int(row.value)
        return latest

    def _upsert_offer(self, product: Product, candidate: CandidateOffer) -> Offer:
        seller = (
            self.db.query(Seller)
            .filter(Seller.allegro_seller_id == candidate.seller_id)
            .one_or_none()
        )
        if seller is None:
            seller = Seller(allegro_seller_id=candidate.seller_id)
        seller.login = candidate.seller_login
        seller.company = candidate.seller_company
        seller.super_seller = candidate.seller_super
        self.db.add(seller)
        self.db.flush()

        offer = (
            self.db.query(Offer).filter(Offer.allegro_offer_id == candidate.offer_id).one_or_none()
        )
        if offer is None:
            offer = Offer(
                allegro_offer_id=candidate.offer_id,
                product_id=product.id,
                name=candidate.name,
                url=candidate.url,
                price=candidate.price,
            )
        offer.product_id = product.id
        offer.seller_id = seller.id
        offer.name = candidate.name
        offer.url = candidate.url
        offer.price = candidate.price
        offer.currency = candidate.currency
        offer.delivery_price = candidate.delivery_price
        offer.total_price = candidate.total_price
        offer.carrier = candidate.carrier
        offer.active = candidate.active
        offer.available = candidate.available
        offer.popularity = candidate.popularity
        offer.popularity_range = candidate.popularity_range
        offer.demand_signal = "sellingMode.popularity" if candidate.popularity is not None else None
        offer.identity_confidence = candidate.identity_confidence
        offer.raw_data = candidate.raw
        offer.checked_at = candidate.observed_at or datetime.now(UTC)
        self.db.add(offer)
        self.db.flush()
        return offer

    def _evidence(
        self,
        product_id: int,
        offer_id: int | None,
        field: str,
        value: Any,
        candidate: CandidateOffer,
        confidence: str,
    ) -> None:
        self.db.add(
            Evidence(
                product_id=product_id,
                offer_id=offer_id,
                field=field,
                value=value,
                source_type=candidate.source_type,
                source_id=candidate.offer_id,
                source_url=candidate.url,
                confidence=confidence,
                observed_at=candidate.observed_at or datetime.now(UTC),
            )
        )

    def _persist_group(
        self, group: ProductGroup
    ) -> tuple[Product, dict[str, Offer], bool, dict[str, Any]]:
        product, is_new = self._upsert_product(group)
        manual = self._apply_manual_evidence(product, group)
        db_offers: dict[str, Offer] = {}
        for candidate in group.offers:
            offer = self._upsert_offer(product, candidate)
            db_offers[candidate.offer_id] = offer
            self._evidence(product.id, offer.id, "price", candidate.price, candidate, "HIGH")
            if candidate.delivery_price is not None:
                self._evidence(
                    product.id,
                    offer.id,
                    "delivery_price",
                    candidate.delivery_price,
                    candidate,
                    "HIGH",
                )
            if candidate.carrier:
                self._evidence(
                    product.id, offer.id, "carrier", candidate.carrier, candidate, "HIGH"
                )
            if candidate.popularity is not None:
                self._evidence(
                    product.id, offer.id, "demand", candidate.popularity, candidate, "HIGH"
                )
        lead = group.offers[0]
        if lead.product_id:
            self._evidence(product.id, None, "identity", lead.product_id, lead, "HIGH")
        if lead.ean:
            self._evidence(product.id, None, "ean", lead.ean, lead, "HIGH")
        if lead.ce_evidence:
            self._evidence(product.id, None, "ce", lead.ce_evidence, lead, "HIGH")
        if lead.generic_evidence is not None:
            self._evidence(product.id, None, "generic", lead.generic_evidence, lead, "HIGH")
        self.db.commit()
        return product, db_offers, is_new, manual

    async def _external(self, product: Product) -> list[ExternalCompetition]:
        rows: list[ExternalCompetition] = []
        for provider in (ManualExternalProvider("Temu"), ManualExternalProvider("AliExpress")):
            check = await provider.search(product.name, product.ean)
            row = (
                self.db.query(ExternalCompetition)
                .filter(
                    ExternalCompetition.product_id == product.id,
                    ExternalCompetition.provider == check.provider,
                )
                .one_or_none()
            ) or ExternalCompetition(product_id=product.id, provider=check.provider)
            row.status = check.status
            row.price = check.price
            row.url = check.url
            row.risk = check.risk
            row.checked_at = datetime.now(UTC)
            self.db.add(row)
            rows.append(row)
        self.db.commit()
        return rows

    def _identity_check(self, group: ProductGroup, product: Product) -> CheckOutcome:
        if group.identity_confidence == "HIGH" or product.allegro_product_id or product.ean:
            return CheckOutcome(
                "PASS",
                "identity",
                f"Tożsamość potwierdzona: {group.identity_basis if group.identity_confidence == 'HIGH' else 'manual source'}",
            )
        return CheckOutcome(
            "VERIFY",
            "identity",
            f"Identyczność wymaga sprawdzenia ({group.identity_basis})",
        )

    def _generic_check(self, group: ProductGroup, product: Product) -> CheckOutcome:
        if product.is_generic is True:
            return CheckOutcome("PASS", "generic", "Produkt generic/no-name potwierdzony źródłem")
        if product.is_generic is False:
            return CheckOutcome("FAIL", "generic", "Produkt nie spełnia kryterium generic/no-name")
        values = {
            offer.generic_evidence for offer in group.offers if offer.generic_evidence is not None
        }
        if values == {True}:
            return CheckOutcome("PASS", "generic", "Produkt generic/no-name potwierdzony źródłem")
        if False in values:
            return CheckOutcome("FAIL", "generic", "Produkt nie spełnia kryterium generic/no-name")
        return CheckOutcome(
            "VERIFY",
            "generic",
            "Brak wiarygodnego potwierdzenia, że produkt nadaje się do odsprzedaży",
        )

    async def _analyze_group(self, group: ProductGroup, scan: ScanRun) -> tuple[str, bool]:
        product, db_offers, is_new, manual = self._persist_group(group)
        identity_confirmed = bool(
            group.identity_confidence == "HIGH" or product.allegro_product_id or product.ean
        )
        checks: list[CheckOutcome] = [
            self._generic_check(group, product),
            self._identity_check(group, product),
        ]

        demand = validate_demand(group.offers, self.settings.min_sellers, self.settings.min_demand)
        competition = validate_competition(group.offers, self.settings.max_competition)
        if not identity_confirmed:
            if demand.state == "FAIL":
                demand = CheckOutcome(
                    "VERIFY",
                    "demand",
                    "Popyt jest niejednoznaczny, bo grupowanie identycznego produktu nie zostało potwierdzone",
                    demand.data,
                )
            competition = CheckOutcome(
                "VERIFY",
                "competition",
                "Dokładna liczba ofert wymaga potwierdzonej tożsamości produktu",
                competition.data,
            )
        checks.extend([demand, competition])

        cheapest = find_cheapest(group.offers)
        if cheapest:
            checks.append(
                CheckOutcome(
                    "PASS",
                    "cheapest",
                    f"Najtańsza oferta: {cheapest.total_price:.2f} PLN łącznie",
                    {"offer_id": cheapest.offer_id, "url": cheapest.url},
                )
            )
        else:
            checks.append(
                CheckOutcome(
                    "VERIFY",
                    "cheapest",
                    "Brak potwierdzonej ceny łącznej aktywnej oferty źródłowej",
                )
            )
        shipping = validate_shipping(cheapest, self.settings.accepted_carriers)
        if manual.get("ce") in {"CE_CONFIRMED", "CE_NOT_REQUIRED", "CE_FAIL"}:
            ce_value = manual["ce"]
            ce = CheckOutcome(
                "FAIL" if ce_value == "CE_FAIL" else "PASS",
                "ce",
                f"Status CE potwierdzony ręcznym źródłem: {ce_value}",
                {"ce_status": ce_value},
            )
        else:
            ce = validate_ce(group.offers, self.settings.require_ce_when_applicable)
        checks.extend([shipping, ce])

        sale_price, price_method, price_check = realistic_sale_price(
            group.offers, self.settings.min_demand
        )
        if manual.get("sale_price") is not None:
            sale_price = float(manual["sale_price"])
            price_method = "manual verified successful-offer price"
            price_check = CheckOutcome(
                "PASS",
                "sale_price",
                f"Realistyczna cena sprzedaży potwierdzona ręcznym źródłem: {sale_price:.2f} PLN",
            )
        if cheapest and cheapest.total_price is not None:
            if (
                self.settings.purchase_price_min is not None
                and cheapest.total_price < self.settings.purchase_price_min
            ):
                checks.append(
                    CheckOutcome(
                        "FAIL",
                        "purchase_price_range",
                        f"Cena zakupu {cheapest.total_price:.2f} PLN jest niższa niż ustawione minimum",
                    )
                )
            if (
                self.settings.purchase_price_max is not None
                and cheapest.total_price > self.settings.purchase_price_max
            ):
                checks.append(
                    CheckOutcome(
                        "FAIL",
                        "purchase_price_range",
                        f"Cena zakupu {cheapest.total_price:.2f} PLN przekracza ustawione maksimum",
                    )
                )
        if sale_price is not None:
            if (
                self.settings.sale_price_min is not None
                and sale_price < self.settings.sale_price_min
            ):
                checks.append(
                    CheckOutcome(
                        "FAIL",
                        "sale_price_range",
                        f"Cena sprzedaży {sale_price:.2f} PLN jest niższa niż ustawione minimum",
                    )
                )
            if (
                self.settings.sale_price_max is not None
                and sale_price > self.settings.sale_price_max
            ):
                checks.append(
                    CheckOutcome(
                        "FAIL",
                        "sale_price_range",
                        f"Cena sprzedaży {sale_price:.2f} PLN przekracza ustawione maksimum",
                    )
                )
        checks.append(price_check)
        breakdown = None
        margin_check = CheckOutcome(
            "VERIFY", "margin", "Nie można wyliczyć zysku bez pełnych danych kosztowych"
        )
        if sale_price is not None and cheapest and cheapest.delivery_price is not None:
            breakdown = calculate_margin(
                sale_price=sale_price,
                purchase_price=cheapest.price,
                delivery=cheapest.delivery_price,
                commission_rate=self.settings.commission_rate,
                other_fees=self.settings.other_fees,
                tax_rate=self.settings.tax_rate,
            )
            margin_check = validate_margin(
                breakdown, self.settings.min_profit, self.settings.min_roi
            )
        checks.append(margin_check)

        await self._external(product)
        status, confidence, passed, failed, verify = final_status(checks)
        active_count = competition.data.get("active_offer_count")
        total_demand = (
            sum(item.get("value") or 0 for item in demand.data.get("confirmed", [])) or None
        )
        score = ranking_score(
            status,
            breakdown.profit if breakdown else None,
            breakdown.roi if breakdown else None,
            total_demand,
            active_count,
            confidence,
        )

        watch = self.db.query(Watchlist).filter(Watchlist.product_id == product.id).one_or_none()
        previous = (
            self.db.query(ResearchResult)
            .filter(ResearchResult.product_id == product.id)
            .order_by(ResearchResult.checked_at.desc())
            .first()
        )
        is_new_opportunity = bool(
            watch and previous and status == "PASS" and previous.status != "PASS"
        )

        result = ResearchResult(
            product_id=product.id,
            scan_run_id=scan.id,
            status=status,
            confidence=confidence,
            cheapest_offer_id=db_offers[cheapest.offer_id].id if cheapest else None,
            realistic_sale_price=sale_price,
            realistic_price_method=price_method,
            purchase_price=breakdown.purchase_price
            if breakdown
            else (cheapest.price if cheapest else None),
            delivery_price=breakdown.delivery
            if breakdown
            else (cheapest.delivery_price if cheapest else None),
            commission=breakdown.commission if breakdown else None,
            other_fees=breakdown.other_fees if breakdown else self.settings.other_fees,
            taxes=breakdown.taxes if breakdown else None,
            profit=breakdown.profit if breakdown else None,
            roi=breakdown.roi if breakdown else None,
            offer_count=active_count,
            demand_sellers=demand.data.get("confirmed", []),
            ce_status=ce.data.get("ce_status", "CE VERIFY"),
            ce_source=(group.offers[0].url if ce.state == "PASS" else None),
            passed_checks=passed,
            failed_checks=failed,
            verification_checks=verify,
            ranking_score=score,
            is_new_opportunity=is_new_opportunity,
        )
        self.db.add(result)
        self.db.add(
            ProductMetric(
                product_id=product.id,
                scan_run_id=scan.id,
                active_offer_count=active_count,
                confirmed_seller_count=len(demand.data.get("confirmed", [])),
                total_popularity=total_demand,
                cheapest_total=cheapest.total_price if cheapest else None,
                realistic_sell_price=sale_price,
                profit=breakdown.profit if breakdown else None,
                roi=breakdown.roi if breakdown else None,
            )
        )
        self.db.add(
            PriceHistory(
                product_id=product.id,
                purchase_price=cheapest.total_price if cheapest else None,
                sale_price=sale_price,
                offer_count=active_count,
                profit=breakdown.profit if breakdown else None,
                demand=total_demand,
            )
        )
        self.db.commit()

        if status == "FAIL":
            write_log(
                self.db,
                "INFO",
                "PRODUCT_REJECTED",
                f"Produkt odrzucony: {product.name}",
                scan.id,
                {"product_id": product.id, "reasons": failed},
            )

        for check in checks:
            if check.state == "VERIFY":
                offer_db_id = (
                    db_offers[cheapest.offer_id].id
                    if cheapest and check.code == "shipping"
                    else None
                )
                source_url = cheapest.url if cheapest else group.offers[0].url
                self.browser.queue(check.code, check.message, source_url, product.id, offer_db_id)

        if watch:
            watch.last_status = status
            self.db.add(watch)
            self.db.commit()
        if is_new_opportunity:
            write_log(
                self.db,
                "INFO",
                "NEW_OPPORTUNITY",
                f"Obserwowany produkt przeszedł do PASS: {product.name}",
                scan.id,
                {"product_id": product.id, "result_id": result.id},
            )
        return status, is_new

    async def run(self, scan: ScanRun, candidates: list[CandidateOffer]) -> None:
        groups = group_products(candidates)
        scan.scanned_count = len(groups)
        scan.status = "RUNNING"
        scan.started_at = scan.started_at or datetime.now(UTC)
        self.db.add(scan)
        self.db.commit()
        write_log(
            self.db,
            "INFO",
            "SCAN_STARTED",
            f"Rozpoczęto analizę {len(groups)} grup produktów",
            scan.id,
            {"mode": scan.mode, "candidate_offers": len(candidates)},
        )

        self._update_scan(scan, "GROUP PRODUCT", 10)
        counts = {"PASS": 0, "FAIL": 0, "VERIFY": 0}
        new_count = 0
        for index, group in enumerate(groups):
            try:
                status, is_new = await self._analyze_group(group, scan)
                counts[status] += 1
                new_count += int(is_new)
            except Exception as exc:  # one product must never stop a scan
                counts["VERIFY"] += 1
                write_log(
                    self.db,
                    "ERROR",
                    "PRODUCT_ANALYSIS_ERROR",
                    f"Produkt pominięty po błędzie: {type(exc).__name__}",
                    scan.id,
                    {"group_key": group.key},
                )
            progress = 10 + int(85 * (index + 1) / max(len(groups), 1))
            self._update_scan(scan, "FINAL VALIDATION", progress)

        scan.pass_count = counts["PASS"]
        scan.fail_count = counts["FAIL"]
        scan.verify_count = counts["VERIFY"]
        scan.new_count = new_count
        scan.status = "COMPLETED"
        scan.pipeline_stage = "COMPLETED"
        scan.progress = 100
        scan.completed_at = datetime.now(UTC)
        self.db.add(scan)
        self.db.commit()
        write_log(
            self.db,
            "INFO",
            "SCAN_COMPLETED",
            f"Skan zakończony: PASS {scan.pass_count}, FAIL {scan.fail_count}, VERIFY {scan.verify_count}",
            scan.id,
        )
