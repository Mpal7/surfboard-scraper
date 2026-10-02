import re

import pytest

from config.settings import KITE_SEARCH_TERMS, SKIP_ADS_TERMS
from src.scraper import classify_board_type

SKIP_CASES = [
    "Tavola da snowboard Rossignol",
    "tavola da windsurf completo",
    "tavola SUP surf gonfiabile",
    "Stand up paddle board",
    "skateboard nuovo",
    "bodyboard per bambini",
    "wakeboard 140 cm",
    "efoil board 6m",
    "hydrofoil board 1200",
]

ALLOW_CASES = [
    "Tavola da surf Firewire",
    "Kite surf quasi mai usato",
    "Tavola KITEFOIL 500",
    "Surf wingfoil 4'2",
    "longboard softboard",
    "parawing 6m",
]


@pytest.mark.parametrize("text", SKIP_CASES)
def test_skip_ads_terms_hard_skip(text):
    skipped = any(
        re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)
        for term in SKIP_ADS_TERMS
    )
    assert skipped, f"{text} should be hard-skipped"


@pytest.mark.parametrize("text", ALLOW_CASES)
def test_skip_ads_terms_allow_surf_foil_kite(text):
    skipped = any(
        re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)
        for term in SKIP_ADS_TERMS
    )
    assert not skipped, f"{text} should not be hard-skipped"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Kite surf completo con vela", "kite"),
        ("Tavola KITEFOIL 500", "kite"),
        ("Surf wingfoil 4'2", "foil"),
        ("hydrofoil board", "foil"),
        ("Tavola da surf Firewire 5'10", "surf"),
        ("longboard classico", "surf"),
        ("", "surf"),
        (None, "surf"),
    ],
)
def test_classify_board_type(text, expected):
    assert classify_board_type(text) == expected


def test_parawing_and_lowwing_are_kite_search_terms():
    assert {"parawing", "lowwing"}.issubset(KITE_SEARCH_TERMS)
