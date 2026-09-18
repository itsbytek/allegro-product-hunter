from __future__ import annotations

from .domain import CandidateOffer, CheckOutcome


def normalize_carrier(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_shipping(offer: CandidateOffer | None, accepted_carriers: list[str]) -> CheckOutcome:
    if offer is None:
        return CheckOutcome(
            "VERIFY", "shipping", "Nie znaleziono możliwej do potwierdzenia oferty źródłowej"
        )
    if offer.delivery_price is None:
        return CheckOutcome(
            "VERIFY",
            "shipping",
            "Brak potwierdzonego obowiązkowego kosztu dostawy",
            {"offer_id": offer.offer_id},
        )
    if not offer.carrier:
        return CheckOutcome(
            "VERIFY",
            "shipping",
            "Allegro listing API nie wskazuje przewoźnika tej konkretnej oferty; wymagana weryfikacja",
            {"offer_id": offer.offer_id, "delivery_price": offer.delivery_price},
        )
    carrier = normalize_carrier(offer.carrier)
    if any(
        normalize_carrier(accepted) in carrier or carrier in normalize_carrier(accepted)
        for accepted in accepted_carriers
    ):
        return CheckOutcome(
            "PASS", "shipping", f"Akceptowana metoda: {offer.carrier}", {"carrier": offer.carrier}
        )
    return CheckOutcome(
        "FAIL",
        "shipping",
        f"Nieakceptowana metoda dostawy: {offer.carrier}",
        {"carrier": offer.carrier},
    )


def find_cheapest(offers: list[CandidateOffer]) -> CandidateOffer | None:
    valid = [
        offer
        for offer in offers
        if offer.active
        and (offer.available is None or offer.available > 0)
        and offer.total_price is not None
    ]
    return min(valid, key=lambda offer: offer.total_price or float("inf"), default=None)
