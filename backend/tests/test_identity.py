from app.services.domain import CandidateOffer
from app.services.identity import group_products


def offer(offer_id: str, *, product_id=None, ean=None, name="Organizer 6 sztuk"):
    return CandidateOffer(
        offer_id=offer_id,
        name=name,
        seller_id=offer_id,
        seller_login=offer_id,
        price=10,
        delivery_price=5,
        currency="PLN",
        url=f"https://example.invalid/{offer_id}",
        product_id=product_id,
        ean=ean,
    )


def test_product_id_has_identity_priority():
    groups = group_products(
        [
            offer("a", product_id="p1", ean="111"),
            offer("b", product_id="p1", ean="222"),
        ]
    )
    assert len(groups) == 1
    assert groups[0].identity_confidence == "HIGH"
    assert groups[0].identity_basis == "Allegro Product ID"


def test_title_only_is_never_high_confidence():
    groups = group_products([offer("a"), offer("b")])
    assert len(groups) == 1
    assert groups[0].identity_confidence == "LOW"
