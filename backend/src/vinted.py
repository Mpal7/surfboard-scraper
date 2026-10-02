"""Vinted-specific scraping helpers.

Vinted is a second marketplace source alongside Subito. Unlike Subito, its
catalog pages are plain server-rendered HTML (no ``__NEXT_DATA__`` payload),
so listings and detail descriptions are parsed from the DOM.

Kept out of ``extraction/`` on purpose: these functions parse marketplace
markup, they are not pure attribute extractors.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

VINTED_ITEM_HOST = "https://www.vinted.it"

# Matches "8.00 €", "€ 8,00" and friends so price tokens can be removed before
# attribute extraction (Vinted descriptions sometimes embed the price, which
# otherwise reads as a board length).
PRICE_REGEX = re.compile(
    r"(?:(?P<prefix>\d[\d.,]*)\s*(?:€|euro|\u20AC)|(?:€|euro|\u20AC)\s*(?P<suffix>\d[\d.,]*))",
    re.IGNORECASE,
)


def strip_price_mentions(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", PRICE_REGEX.sub(" ", text)).strip()


def _normalize_text_candidate(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _collect_json_descriptions(payload, candidates: list[str]) -> None:
    if isinstance(payload, dict):
        description = payload.get("description")
        if isinstance(description, str):
            candidates.append(description)
        for value in payload.values():
            _collect_json_descriptions(value, candidates)
        return

    if isinstance(payload, list):
        for item in payload:
            _collect_json_descriptions(item, candidates)


def _vinted_description_score(text: str) -> tuple[int, int, int]:
    lowered = text.lower()
    has_dimension_signal = bool(
        re.search(r"\b\d{1,2}\s*(?:'|’|′|ft|feet|foot|piedi)\s*\d{0,2}", text)
        or re.search(r"\b\d{1,2}[.,]\d{1,2}\s*x\s*\d", text)
        or re.search(r"\b\d{2,3}\s*cm\b", text, re.IGNORECASE)
    )
    has_board_signal = any(
        token in lowered
        for token in ("tavola", "surfboard", "shortboard", "longboard", "softboard")
    )
    return (int(has_dimension_signal), int(has_board_signal), len(text))


def extract_detail_description(soup: BeautifulSoup) -> str:
    """Pick the richest description text available on a Vinted detail page."""
    candidates: list[str] = []

    def add_candidate(raw_text: str | None) -> None:
        text = _normalize_text_candidate(raw_text)
        if text and text not in candidates:
            candidates.append(text)

    for attrs in (
        {"itemprop": "description"},
        {"property": "og:description"},
        {"name": "description"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            add_candidate(meta.get("content"))

    for script_tag in soup.find_all("script", type="application/ld+json"):
        raw_payload = script_tag.string or script_tag.get_text()
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue
        json_candidates: list[str] = []
        _collect_json_descriptions(payload, json_candidates)
        for candidate in json_candidates:
            add_candidate(candidate)

    for node in soup.find_all(attrs={"data-testid": re.compile("description", re.IGNORECASE)}):
        add_candidate(node.get_text(separator=" ", strip=True))

    for node in soup.find_all(
        ["p", "div"],
        class_=lambda cls: cls
        and (
            "description" in cls.lower()
            if isinstance(cls, str)
            else any("description" in part.lower() for part in cls)
        ),
    ):
        add_candidate(node.get_text(separator=" ", strip=True))

    for node in soup.find_all("p"):
        add_candidate(node.get_text(separator=" ", strip=True))

    if not candidates:
        return ""

    return max(candidates, key=_vinted_description_score)


def extract_listings_from_html(soup: BeautifulSoup) -> list[dict]:
    """Return raw listing dicts shaped like Subito's scraper listings."""
    listings: list[dict] = []
    seen_links: set[str] = set()

    for link_tag in soup.find_all("a", href=True):
        href = (link_tag.get("href") or "").strip()
        if "/items/" not in href:
            continue

        if href.startswith("/"):
            href = VINTED_ITEM_HOST + href
        href = href.split("?", 1)[0]
        if href in seen_links:
            continue

        title = (link_tag.get("title") or "").strip()
        model = title.split(",")[0].strip() if title else "N/A"

        image_url = None
        parent = link_tag.parent
        if parent:
            image_tag = parent.find("img")
            if image_tag and image_tag.get("src"):
                image_url = image_tag["src"]

        listings.append(
            {
                "source": "vinted",
                "marketplace": "vinted",
                "link": href,
                "model": model,
                "full_text": title,
                "image_url": image_url,
                "location_text": None,
            }
        )
        seen_links.add(href)

    return listings
