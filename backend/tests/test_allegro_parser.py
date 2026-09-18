import json
from pathlib import Path

from app.services.allegro import parse_listing


def test_parser_uses_real_allegro_listing_shape():
    fixture = Path(__file__).parent / "fixtures" / "allegro_listing.json"
    offers = parse_listing(json.loads(fixture.read_text(encoding="utf-8")))
    assert len(offers) == 1
    offer = offers[0]
    assert offer.offer_id == "7781902469"
    assert offer.price == 145.13
    assert offer.delivery_price == 1.0
    assert offer.popularity == 42
    assert offer.seller_login == "hivionics"
    assert offer.url == "https://allegro.pl/oferta/7781902469"
    assert offer.carrier is None  # the listing payload does not prove a carrier


def test_parser_does_not_invent_missing_delivery():
    payload = {
        "items": {
            "regular": [
                {
                    "id": "1",
                    "name": "X",
                    "seller": {"id": "2"},
                    "sellingMode": {"price": {"amount": "10", "currency": "PLN"}},
                    "delivery": {"availableForFree": False},
                }
            ],
            "promoted": [],
        }
    }
    offer = parse_listing(payload)[0]
    assert offer.delivery_price is None
    assert offer.total_price is None
