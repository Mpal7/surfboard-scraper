"""Data-quality cleanup for Ads scraped from Vinted.

Vinted catalog titles are sparse and sometimes misleading: a price token can be
read as a board length, and accessory/non-board items can slip past keyword
gating. This module flags and hides those stored Ads without touching Subito.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from config.settings import MAINTENANCE_LOG_DIR
from src.models import Ad
from utils.logger import get_logger

logger = get_logger(__name__, MAINTENANCE_LOG_DIR)

VINTED_NON_BOARD_TITLE_MARKERS = (
    "t-shirt",
    "tshirt",
    "shirt",
    "felpa",
    "hoodie",
    "sweatshirt",
    "jacke",
    "jacket",
    "maglia",
    "rash guard",
    "cap",
    "cappello",
    "leash",
    "fins",
    "fin",
    "pinna",
    "pinne",
    "rack",
    "bike rack",
    "costume",
    "shorts",
    "pants",
    "boardshort",
    "bag",
    "boardbag",
    "boardbags",
    "cinto",
    "belt",
    "keychain",
    "portachiavi",
    "porte clef",
    "collana",
    "collanine",
    "calamita",
    "gadget",
    "miniatura",
    "mini tavola",
    "quadro",
    "poster",
    "decor",
    "arredamento",
    "display",
    "wall",
    "deck",
    "toy",
    "gioco",
    "barbie",
    "ken",
    "libro",
    "book",
    "pokemon",
    "pikachu",
    "souvenir",
    "stampa 3d",
    "footstrap",
    "foostrap",
)


def _has_supporting_board_dimensions(ad: Ad) -> bool:
    return any(value is not None for value in (ad.width_in, ad.thickness_in, ad.liters))


def _normalize_model(model: str | None) -> str:
    return re.sub(r"\s+", " ", (model or "").lower()).strip()


def _title_contains_non_board_marker(model: str | None) -> bool:
    normalized = _normalize_model(model)
    if not normalized:
        return False
    return any(marker in normalized for marker in VINTED_NON_BOARD_TITLE_MARKERS)


def _price_looks_like_length(ad: Ad) -> bool:
    if _has_supporting_board_dimensions(ad):
        return False
    if ad.price is None or ad.length_ft is None:
        return False

    try:
        price = float(ad.price)
        feet = int(ad.length_ft)
        inches = float(ad.length_in or 0)
    except (TypeError, ValueError):
        return False

    if not (4 <= feet <= 10):
        return False

    return abs(price - (feet + inches / 100.0)) < 0.011


def _has_invalid_board_length(ad: Ad) -> bool:
    if _has_supporting_board_dimensions(ad):
        return False
    if ad.length_ft is None:
        return False

    try:
        feet = int(ad.length_ft)
    except (TypeError, ValueError):
        return False

    return feet < 4 or feet > 10


def classify_vinted_cleanup_reasons(ad: Ad) -> list[str]:
    if ad.source != "vinted" or not ad.is_visible:
        return []

    reasons: list[str] = []
    if _price_looks_like_length(ad):
        reasons.append("price_like_length")
    if _has_invalid_board_length(ad):
        reasons.append("invalid_length_without_support")
    if not _has_supporting_board_dimensions(ad) and _title_contains_non_board_marker(ad.model):
        reasons.append("obvious_non_board_title")
    return reasons


def _clear_board_metrics(ad: Ad) -> None:
    ad.length_ft = None
    ad.length_in = None
    ad.width_in = None
    ad.thickness_in = None
    ad.liters = None


def cleanup_vinted_ads(
    db: Session,
    *,
    dry_run: bool = False,
    service_logger=logger,
) -> dict:
    ads_to_review = db.query(Ad).filter(Ad.source == "vinted", Ad.is_visible == True).all()
    if not ads_to_review:
        service_logger.info("No visible Vinted ads found. Exiting.")
        return {
            "scanned_ads": 0,
            "hidden_ads": 0,
            "price_like_matches": 0,
            "obvious_non_board_matches": 0,
            "invalid_length_matches": 0,
            "sample_links": [],
            "dry_run": dry_run,
        }

    service_logger.info("Reviewing %d visible Vinted ads for cleanup.", len(ads_to_review))
    hidden_ads = 0
    price_like_matches = 0
    obvious_non_board_matches = 0
    invalid_length_matches = 0
    sample_links: list[str] = []

    for ad in ads_to_review:
        reasons = classify_vinted_cleanup_reasons(ad)
        if not reasons:
            continue

        hidden_ads += 1
        if "price_like_length" in reasons:
            price_like_matches += 1
        if "invalid_length_without_support" in reasons:
            invalid_length_matches += 1
        if "obvious_non_board_title" in reasons:
            obvious_non_board_matches += 1

        if len(sample_links) < 20 and ad.link:
            sample_links.append(ad.link)

        service_logger.info("Hiding Vinted ad ID %s (%s): %s", ad.id, ad.link, ", ".join(reasons))
        if dry_run:
            continue

        ad.is_visible = False
        _clear_board_metrics(ad)

    if dry_run:
        service_logger.info("Dry run complete. Would hide %d ads.", hidden_ads)
    elif hidden_ads > 0:
        db.commit()
        service_logger.info("Committed cleanup for %d Vinted ads.", hidden_ads)
    else:
        service_logger.info("No Vinted ads required cleanup.")

    return {
        "scanned_ads": len(ads_to_review),
        "hidden_ads": hidden_ads,
        "price_like_matches": price_like_matches,
        "obvious_non_board_matches": obvious_non_board_matches,
        "invalid_length_matches": invalid_length_matches,
        "sample_links": sample_links,
        "dry_run": dry_run,
    }
