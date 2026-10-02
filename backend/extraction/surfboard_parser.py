"""Deep module wrapping all equipment extraction behind one interface.

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
    extract_board_dimensions_cm,
    extract_foil_area_cm2,
    extract_foil_wingspan_cm,
    extract_liters,
    extract_mast_length_cm,
    extract_price,
    extract_wing_area_m2,
    find_brand,
    normalize_for_matching,
    parse_dimension_part,
    text_pre_processor,
)


def parse_listing(text: str) -> dict[str, Any]:
    """Extract all supported equipment attributes from Ad text.

    Missing values are represented by ``None``. Surfboard dimensions retain
    their existing fields; foil/kite sizes use explicit metric fields.
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
            'foil_area_cm2': None,
            'mast_length_cm': None,
            'foil_wingspan_cm': None,
            'wing_area_m2': None,
            'board_length_cm': None,
            'board_width_cm': None,
        }

    dims = extract_dimensions(text) or {}
    board_dims = extract_board_dimensions_cm(text) or {}

    return {
        'price': extract_price(text),
        'brand': find_brand(text),
        'liters': extract_liters(text),
        'length_ft': dims.get('length_ft'),
        'length_in': dims.get('length_in'),
        'width_in': dims.get('width_in'),
        'thickness_in': dims.get('thickness_in'),
        'foil_area_cm2': extract_foil_area_cm2(text),
        'mast_length_cm': extract_mast_length_cm(text),
        'foil_wingspan_cm': extract_foil_wingspan_cm(text),
        'wing_area_m2': extract_wing_area_m2(text),
        'board_length_cm': board_dims.get('board_length_cm'),
        'board_width_cm': board_dims.get('board_width_cm'),
    }
