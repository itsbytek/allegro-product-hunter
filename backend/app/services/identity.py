from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from typing import Any

from .domain import CandidateOffer, ProductGroup

CRITICAL_PARAMETER_NAMES = {
    "model",
    "kod producenta",
    "manufacturer code",
    "rozmiar",
    "wymiary",
    "materiał",
    "material",
    "pojemność",
    "capacity",
    "kolor",
    "color",
    "liczba sztuk",
    "liczba elementów",
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_like = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_like).strip()


def canonical_parameters(parameters: dict[str, Any]) -> str:
    selected: list[tuple[str, str]] = []
    for key, value in parameters.items():
        normalized_key = normalize_text(str(key))
        if normalized_key in {normalize_text(item) for item in CRITICAL_PARAMETER_NAMES}:
            selected.append((normalized_key, normalize_text(str(value))))
    return "|".join(f"{key}={value}" for key, value in sorted(selected))


def identity_key(offer: CandidateOffer) -> tuple[str, str, str]:
    if offer.product_id:
        return f"product:{offer.product_id}", "HIGH", "Allegro Product ID"
    if offer.ean:
        return f"ean:{offer.ean}", "HIGH", "EAN/GTIN"
    if offer.model and canonical_parameters(offer.parameters):
        raw = f"{normalize_text(offer.model)}|{canonical_parameters(offer.parameters)}"
        return (
            f"model:{hashlib.sha256(raw.encode()).hexdigest()[:24]}",
            "MEDIUM",
            "model + parameters",
        )
    params = canonical_parameters(offer.parameters)
    if params:
        raw = f"{normalize_text(offer.name)}|{params}"
        return (
            f"params:{hashlib.sha256(raw.encode()).hexdigest()[:24]}",
            "MEDIUM",
            "exact parameters",
        )
    # Title is only an auxiliary signal and can never make the final decision PASS.
    title = normalize_text(offer.name)
    return f"title:{hashlib.sha256(title.encode()).hexdigest()[:24]}", "LOW", "title only"


def group_products(offers: list[CandidateOffer]) -> list[ProductGroup]:
    buckets: dict[str, list[CandidateOffer]] = defaultdict(list)
    metadata: dict[str, tuple[str, str]] = {}
    for offer in offers:
        key, confidence, basis = identity_key(offer)
        offer.identity_confidence = confidence
        buckets[key].append(offer)
        metadata[key] = confidence, basis
    return [
        ProductGroup(
            key=key,
            offers=items,
            identity_confidence=metadata[key][0],
            identity_basis=metadata[key][1],
        )
        for key, items in buckets.items()
    ]
