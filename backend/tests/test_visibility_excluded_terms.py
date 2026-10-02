"""Visibility rules for accessory terms on surf Ads.

Regression tests for a bug found during practical verification: real
surfboards were hidden from the UI because their descriptions mentioned
included extras ("completa di pinne e pad", "sacca FCS inclusa"). Accessory
terms must only disqualify a surf Ad when they describe the Ad itself.
"""

from unittest.mock import MagicMock

from src.models import Ad
from src.scraper import _ingest_listing, _reconcile_existing_ad


def test_reconcile_keeps_board_with_included_accessories_visible():
    ad = Ad(
        model="Tavola da surf Franz Minimalibu 7'8",
        link="https://example.com/franz",
        board_type="surf",
        is_visible=False,
    )

    changed = _reconcile_existing_ad(
        ad,
        "Vendo Franz Surfboards misura 7'8 x 21 3/4 x 3, completa di pinne e pad, sacca FCS inclusa",
    )

    assert changed
    assert ad.is_visible is True


def test_reconcile_hides_accessory_titled_ad():
    ad = Ad(
        model="Borsa tavola da surf 6'2",
        link="https://example.com/borsa",
        board_type="surf",
        is_visible=True,
    )

    _reconcile_existing_ad(ad, "Borsa tavola da surf 6'2 FCS nuova")

    assert ad.is_visible is False


def test_reconcile_hides_surf_ad_without_board_identity():
    ad = Ad(
        model="Vendo attrezzatura surf",
        link="https://example.com/kit",
        board_type="surf",
        is_visible=True,
    )

    _reconcile_existing_ad(ad, "Vendo attrezzatura surf completa di muta, sacca e pinne")

    assert ad.is_visible is False


def _ingest(listing):
    db = MagicMock()
    ad, _ = _ingest_listing(
        db,
        listing,
        referrer_url="https://example.com/search",
        location_fallback="Roma",
        existing_links=set(),
        existing_ads={},
        fetch_detail=lambda *args, **kwargs: None,
    )
    return ad


def test_ingest_keeps_board_with_included_accessories_visible(mocker):
    mocker.patch("src.scraper.time.sleep")

    ad = _ingest(
        {
            "source": "json",
            "link": "https://example.com/board-320",
            "model": "Tavola da surf 7'8",
            "full_text": "Tavola da surf 7'8 completa di pinne e pad, sacca inclusa 320 €",
            "image_url": None,
            "location_text": "Roma",
        }
    )

    assert ad is not None
    assert ad.is_visible is True
    assert ad.price == 320.0


def test_ingest_hides_accessory_titled_ad(mocker):
    mocker.patch("src.scraper.time.sleep")

    ad = _ingest(
        {
            "source": "json",
            "link": "https://example.com/borsa-62",
            "model": "Borsa tavola da surf 6'2",
            "full_text": "Borsa tavola da surf 6'2 FCS nuova 40 €",
            "image_url": None,
            "location_text": "Roma",
        }
    )

    assert ad is not None
    assert ad.is_visible is False


def test_reconcile_does_not_read_vinted_price_as_length():
    ad = Ad(
        model="Kappe mit Surfboard Logo",
        link="https://www.vinted.it/items/10200414869-kappe",
        source="vinted",
        board_type="surf",
        is_visible=False,
    )

    _reconcile_existing_ad(ad, "Kappe mit Surfboard Logo, 10,00 €")

    assert ad.length_ft is None
    assert ad.is_visible is False


def test_reconcile_keeps_vinted_board_with_price_and_size():
    ad = Ad(
        model="Surfboard Chapman",
        link="https://www.vinted.it/items/10054132450-surfboard",
        source="vinted",
        board_type="surf",
        is_visible=False,
    )

    _reconcile_existing_ad(ad, "Surfboard Chapman 6'1', 60,00 €")

    assert ad.length_ft == 6
    assert ad.is_visible is True


def test_ingest_does_not_read_vinted_price_as_length_when_detail_fetch_fails(mocker):
    mocker.patch("src.scraper.time.sleep")

    ad = _ingest(
        {
            "source": "vinted",
            "marketplace": "vinted",
            "link": "https://www.vinted.it/items/1-kappe",
            "model": "Kappe mit Surfboard Logo",
            "full_text": "Kappe mit Surfboard Logo, 10,00 €",
            "image_url": None,
            "location_text": None,
        }
    )

    assert ad is not None
    assert ad.price == 10.0
    assert ad.length_ft is None
    assert ad.is_visible is False
