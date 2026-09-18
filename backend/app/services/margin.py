from __future__ import annotations

from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal

from .domain import CheckOutcome, MarginBreakdown

MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_margin(
    sale_price: float,
    purchase_price: float,
    delivery: float,
    commission_rate: float,
    other_fees: float = 0,
    tax_rate: float = 0,
) -> MarginBreakdown:
    sale = Decimal(str(sale_price))
    purchase = Decimal(str(purchase_price))
    shipping = Decimal(str(delivery))
    commission = _money(sale * Decimal(str(commission_rate)))
    fees = Decimal(str(other_fees))
    taxes = _money(sale * Decimal(str(tax_rate)))
    profit = _money(sale - purchase - shipping - commission - fees - taxes)
    cost = purchase + shipping + commission + fees + taxes
    roi = _money((profit / cost * Decimal("100")) if cost else Decimal("0"))
    return MarginBreakdown(
        sale_price=float(_money(sale)),
        purchase_price=float(_money(purchase)),
        delivery=float(_money(shipping)),
        commission=float(commission),
        other_fees=float(_money(fees)),
        taxes=float(taxes),
        profit=float(profit),
        roi=float(roi),
    )


def validate_margin(
    breakdown: MarginBreakdown, min_profit: float, min_roi: float | None
) -> CheckOutcome:
    if breakdown.profit < min_profit:
        return CheckOutcome(
            "FAIL",
            "margin",
            f"Zysk {breakdown.profit:.2f} PLN jest niższy niż {min_profit:.2f} PLN",
            {"breakdown": asdict(breakdown)},
        )
    if min_roi is not None and breakdown.roi < min_roi:
        return CheckOutcome(
            "FAIL",
            "margin",
            f"ROI {breakdown.roi:.2f}% jest niższe niż {min_roi:.2f}%",
            {"breakdown": asdict(breakdown)},
        )
    return CheckOutcome(
        "PASS",
        "margin",
        f"Zysk {breakdown.profit:.2f} PLN, ROI {breakdown.roi:.2f}%",
        {"breakdown": asdict(breakdown)},
    )
