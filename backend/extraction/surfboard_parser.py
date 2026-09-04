"""Deep module wrapping all surfboard extraction behind a single interface.

Callers use ``parse_listing(text)`` to get every attribute at once.
Individual extractors are re-exported for backward compatibility but the
intended seam is ``parse_listing``.
"""

from __future__ import annotations

from typing import Any

# Re-export individual extractors so existing callers keep working.
from extraction.extraction import (
    BRAND_MAP,
    BRAND_REGEX,
    FRACTION_MAP,
    FRACTION_SYMBOLS,
    POPULAR_BRANDS,
    create_brand_pattern,
    extract_dimensions,
    extract_liters,
    extract_price,
    find_brand,
    normalize_for_matching,
    parse_dimension_part,
    text_pre_processor,
)


def parse_listing(text: str) -> dict[str, Any]:
    """Extract all surfboard attributes from ad text.

    Returns a dict with keys: price, brand, liters, length_ft, length_in,
    width_in, thickness_in.  Missing values are None.
    """
    if not text:
        return {
            'price': None,
            'brand': None,
            'liters': None,
            'length_ft': None,
            'length_in': None,
            'width_in': None,
            'thickness_in': None,
        }

    dims = extract_dimensions(text) or {}

    return {
        'price': extract_price(text),
        'brand': find_brand(text),
        'liters': extract_liters(text),
        'length_ft': dims.get('length_ft'),
        'length_in': dims.get('length_in'),
        'width_in': dims.get('width_in'),
        'thickness_in': dims.get('thickness_in'),
    }
