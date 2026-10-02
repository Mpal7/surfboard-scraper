import pytest

from extraction.surfboard_parser import parse_listing
from src.models import Ad
from src.scraper import (
    _is_relevant_equipment_ad,
    _reconcile_existing_ad,
    classify_board_type,
    classify_equipment_type,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Gong Curve L V2 (1200 cm2)", {"foil_area_cm2": 1200.0}),
        ("Foil Naish area 1150cmq", {"foil_area_cm2": 1150.0}),
        ("Front wing RRD 1700 cm²", {"foil_area_cm2": 1700.0}),
        ("Ala wing foil gong super sport 9mq", {"wing_area_m2": 9.0}),
        ("Wing North Mode 5.5 m²", {"wing_area_m2": 5.5}),
        ("Kite Ozone Enduro 12mt", {"wing_area_m2": 12.0}),
        ("Kiteboard Nobile 135x44", {"board_length_cm": 135.0, "board_width_cm": 44.0}),
        ("Tavola kitesurf 41x138", {"board_length_cm": 138.0, "board_width_cm": 41.0}),
        ("Foil front 950 + stab 330", {"foil_area_cm2": 950.0}),
        ("Front Wing Reptile 1800", {"foil_area_cm2": 1800.0}),
        ("foil set front da 1300", {"foil_area_cm2": 1300.0}),
        ("Hydrofoil Sabfoil mast carbon 91 cm wingspan 80 cm", {"mast_length_cm": 91.0, "foil_wingspan_cm": 80.0}),
        ("Piantone 65/90 cm", {"mast_length_cm": 65.0}),
        ("KITE SURF ALI Cabrinha misure 13/11/8", {"wing_area_m2": 13.0}),
        ("ala wingfoil safe 6 mq", {"wing_area_m2": 6.0}),
        ("lowwing 6", {"wing_area_m2": 6.0}),
        ("Tavola da kite surf 130cm", {"board_length_cm": 130.0}),
    ],
)
def test_parse_equipment_dimensions(text, expected):
    parsed = parse_listing(text)
    for key, value in expected.items():
        assert parsed[key] == value


def test_foil_model_number_is_not_an_area():
    parsed = parse_listing("Tavola KITEFOIL 500 convertibile in surf")
    assert parsed["foil_area_cm2"] is None
    assert parsed["wing_area_m2"] is None


@pytest.mark.parametrize(
    "text,model,board_type,expected",
    [
        ("Ala wing foil gong super sport 9mq", "Ala wing foil gong super sport 9mq", "foil", True),
        ("Gong Curve L V2 1200 cm2 cover", "Gong foil set V2 Curve L front + cover", "foil", True),
        ("Kiteboard Nobile 135x44", "Kiteboard Nobile 135x44", "kite", True),
        ("Kite surf completo, vela 9mq e tavola", "Set kite surf", "kite", True),
        ("Trapezio Mystic Darkrider kitesurf taglia M", "Trapezio Mystic Darkrider kitesurf", "kite", True),
        ("Muta Mystic per kitesurf", "Muta Mystic kitesurf", "kite", False),
        ("Borsa trasporto per wingfoil", "Borsa wingfoil", "foil", False),
        ("Treciclo artigianale per kitesurf", "Kite surf", "kite", False),
    ],
)
def test_equipment_gate_ignores_accessories(text, model, board_type, expected):
    parsed = parse_listing(text)
    assert _is_relevant_equipment_ad(text, model, board_type, parsed) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Tavola KITEFOIL 500", "kite"),
        ("Ala wing foil Gong 5mq", "foil"),
        ("Kiteboard North 138x42", "kite"),
    ],
)
def test_equipment_classification(text, expected):
    assert classify_board_type(text) == expected


@pytest.mark.parametrize(
    "text,model,expected",
    [
        ("Trapezio Mystic Darkrider kitesurf taglia M", "Trapezio Mystic Darkrider kitesurf", "harness"),
        ("Tavola kitesurf North 138x42", "Tavola kitesurf North", "board"),
        ("Ala wing foil Gong 5mq", "Ala wing foil Gong 5mq", "wing"),
        ("Hydrofoil Sabfoil front wing 1200 cm2", "Hydrofoil Sabfoil front wing", "foil"),
        ("Parawing 6m", "Parawing 6m", "wing"),
        ("Lowwing 6m", "Lowwing 6m", "wing"),
    ],
)
def test_equipment_component_classification(text, model, expected):
    assert classify_equipment_type(text, model) == expected


def test_wingfoil_title_is_relevant_equipment():
    text = "ala wingfoil safe 6 mq 110"
    parsed = parse_listing(text)
    assert classify_board_type(text) == "foil"
    assert _is_relevant_equipment_ad(text, text, "foil", parsed)


@pytest.mark.parametrize("text", ["Parawing 6m", "Lowwing 6m"])
def test_kite_wing_terms_are_classified_as_relevant(text):
    parsed = parse_listing(text)
    assert classify_board_type(text) == "kite"
    assert _is_relevant_equipment_ad(text, text, "kite", parsed)


def test_existing_kite_ad_hidden_by_old_rules_is_reconciled():
    ad = Ad(
        model="Kite surf completo 9 mq",
        board_type="kite",
        equipment_type="kite",
        link="https://example.com/old-kite",
        is_visible=False,
    )

    changed = _reconcile_existing_ad(ad, "Kite surf completo 9 mq")

    assert changed
    assert ad.is_visible is True
    assert ad.wing_area_m2 == 9.0
