from __future__ import annotations

from .domain import CandidateOffer, CheckOutcome


def validate_demand(
    offers: list[CandidateOffer], min_sellers: int, min_demand: int
) -> CheckOutcome:
    best_by_seller: dict[str, CandidateOffer] = {}
    unknown = False
    for offer in offers:
        if not offer.active:
            continue
        if offer.popularity is None:
            unknown = True
            continue
        current = best_by_seller.get(offer.seller_id)
        if current is None or (current.popularity or 0) < offer.popularity:
            best_by_seller[offer.seller_id] = offer

    confirmed = [
        offer for offer in best_by_seller.values() if (offer.popularity or 0) >= min_demand
    ]
    data = {
        "confirmed": [
            {
                "seller_id": offer.seller_id,
                "seller": offer.seller_login or offer.seller_id,
                "value": offer.popularity,
                "signal": "Allegro API sellingMode.popularity",
                "price": offer.price,
                "url": offer.url,
                "offer_id": offer.offer_id,
            }
            for offer in sorted(confirmed, key=lambda item: item.popularity or 0, reverse=True)
        ],
        "required_sellers": min_sellers,
        "threshold": min_demand,
    }
    if len(confirmed) >= min_sellers:
        return CheckOutcome(
            "PASS", "demand", f"Popyt potwierdzony u {len(confirmed)} sprzedawców", data
        )
    if unknown:
        return CheckOutcome(
            "VERIFY",
            "demand",
            f"Potwierdzono {len(confirmed)}/{min_sellers} sprzedawców; część ofert nie ma wiarygodnego wskaźnika popytu",
            data,
        )
    return CheckOutcome(
        "FAIL",
        "demand",
        f"Tylko {len(confirmed)}/{min_sellers} sprzedawców osiąga próg {min_demand}",
        data,
    )
