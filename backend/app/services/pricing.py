from __future__ import annotations

import statistics

from .domain import CandidateOffer, CheckOutcome


def realistic_sale_price(
    offers: list[CandidateOffer], demand_threshold: int
) -> tuple[float | None, str | None, CheckOutcome]:
    successful = [
        offer.price
        for offer in offers
        if offer.active and offer.popularity is not None and offer.popularity >= demand_threshold
    ]
    if not successful:
        return (
            None,
            None,
            CheckOutcome("VERIFY", "sale_price", "Brak cen ofert z potwierdzonym popytem"),
        )
    price = round(float(statistics.median(successful)), 2)
    return (
        price,
        "median confirmed-demand offers",
        CheckOutcome(
            "PASS",
            "sale_price",
            f"Mediana {len(successful)} ofert z potwierdzonym popytem: {price:.2f} PLN",
            {"sample_size": len(successful), "prices": successful, "sale_price": price},
        ),
    )
