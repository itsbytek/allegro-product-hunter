from app.services.competition import validate_competition
from app.services.demand import validate_demand
from app.services.domain import CandidateOffer
from app.services.final_validation import final_status
from app.services.shipping import find_cheapest, validate_shipping


def candidate(
    offer_id: str, seller: str, popularity: int | None, carrier="DPD", price=20, delivery=5
):
    return CandidateOffer(
        offer_id=offer_id,
        name="Ten sam produkt",
        seller_id=seller,
        seller_login=seller,
        price=price,
        delivery_price=delivery,
        currency="PLN",
        url=f"https://example.invalid/{offer_id}",
        popularity=popularity,
        carrier=carrier,
    )


def test_demand_requires_independent_sellers():
    offers = [candidate("a", "seller-1", 100), candidate("b", "seller-1", 200)]
    assert validate_demand(offers, min_sellers=2, min_demand=30).state == "FAIL"
    offers.append(candidate("c", "seller-2", 30))
    outcome = validate_demand(offers, min_sellers=2, min_demand=30)
    assert outcome.state == "PASS"
    assert len(outcome.data["confirmed"]) == 2


def test_missing_demand_data_means_verify_not_fake_zero():
    assert validate_demand([candidate("a", "s", None)], 2, 30).state == "VERIFY"


def test_competition_limit_and_shipping():
    offers = [candidate(str(i), str(i), 40) for i in range(31)]
    assert validate_competition(offers, 30).state == "FAIL"
    cheapest = find_cheapest(
        [candidate("a", "s1", 30, price=15), candidate("b", "s2", 40, price=20)]
    )
    assert cheapest and cheapest.offer_id == "a"
    assert validate_shipping(cheapest, ["DPD"]).state == "PASS"
    cheapest.carrier = None
    assert validate_shipping(cheapest, ["DPD"]).state == "VERIFY"


def test_fail_has_priority_over_verify_in_final_filter():
    checks = [validate_competition([candidate(str(i), str(i), 40) for i in range(31)], 30)]
    unknown_shipping = candidate("x", "s", 10, carrier=None)
    checks.append(validate_shipping(unknown_shipping, ["DPD"]))
    status, *_ = final_status(checks)
    assert status == "FAIL"
