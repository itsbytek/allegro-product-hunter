from __future__ import annotations

from .domain import CandidateOffer, CheckOutcome


def validate_competition(offers: list[CandidateOffer], max_competition: int) -> CheckOutcome:
    active_count = sum(
        1 for offer in offers if offer.active and (offer.available is None or offer.available > 0)
    )
    if active_count > max_competition:
        return CheckOutcome(
            "FAIL",
            "competition",
            f"{active_count} aktywnych ofert przekracza limit {max_competition}",
            {"active_offer_count": active_count},
        )
    return CheckOutcome(
        "PASS",
        "competition",
        f"{active_count} aktywnych ofert mieści się w limicie {max_competition}",
        {"active_offer_count": active_count},
    )
