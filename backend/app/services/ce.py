from __future__ import annotations

from .domain import CandidateOffer, CheckOutcome


def validate_ce(offers: list[CandidateOffer], require_when_applicable: bool = True) -> CheckOutcome:
    values = {offer.ce_evidence for offer in offers if offer.ce_evidence}
    if "CE_FAIL" in values:
        return CheckOutcome(
            "FAIL", "ce", "CE jest wymagane, ale brak zgodności", {"ce_status": "CE FAIL"}
        )
    if "CE_CONFIRMED" in values:
        return CheckOutcome(
            "PASS", "ce", "Zgodność CE potwierdzona źródłem", {"ce_status": "CE CONFIRMED"}
        )
    if "CE_NOT_REQUIRED" in values:
        return CheckOutcome(
            "PASS",
            "ce",
            "Źródło potwierdza, że CE nie jest wymagane",
            {"ce_status": "CE NOT REQUIRED"},
        )
    if not require_when_applicable:
        return CheckOutcome(
            "PASS", "ce", "Weryfikacja CE wyłączona w ustawieniach", {"ce_status": "CE VERIFY"}
        )
    return CheckOutcome(
        "VERIFY",
        "ce",
        "Nie ustalono wiarygodnie, czy produkt wymaga CE",
        {"ce_status": "CE VERIFY"},
    )
