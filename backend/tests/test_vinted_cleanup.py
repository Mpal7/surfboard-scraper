from unittest.mock import MagicMock

from src.models import Ad
from src.vinted_cleanup import classify_vinted_cleanup_reasons, cleanup_vinted_ads


def test_classify_vinted_cleanup_reasons_flags_price_like_length():
    ad = Ad(
        source="vinted",
        model="Tavola da surf",
        price=8.0,
        length_ft=8,
        length_in=0,
        is_visible=True,
    )

    reasons = classify_vinted_cleanup_reasons(ad)

    assert reasons == ["price_like_length"]


def test_classify_vinted_cleanup_reasons_flags_obvious_non_board_title():
    ad = Ad(
        source="vinted",
        model="Pukas Surfboard Sweatshirt Jacke",
        price=13.0,
        is_visible=True,
        brand="Pukas",
    )

    reasons = classify_vinted_cleanup_reasons(ad)

    assert reasons == ["obvious_non_board_title"]


def test_classify_vinted_cleanup_reasons_keeps_real_board_with_supporting_dimensions():
    ad = Ad(
        source="vinted",
        model="Surfboard 5'8 28.5L Mayhem Uberdriver + Fins",
        price=170.0,
        length_ft=5,
        length_in=8,
        liters=28.5,
        is_visible=True,
        brand="Lost Mayhem",
    )

    reasons = classify_vinted_cleanup_reasons(ad)

    assert reasons == []


def test_classify_vinted_cleanup_reasons_ignores_non_vinted_ads():
    ad = Ad(
        source="subito",
        model="Surfboard Keychain",
        price=5.0,
        length_ft=5,
        is_visible=True,
    )

    assert classify_vinted_cleanup_reasons(ad) == []


def test_classify_vinted_cleanup_reasons_flags_invalid_length_without_support():
    ad = Ad(
        source="vinted",
        model="Tavola da surf lunghezza 63 cm",
        price=3.5,
        length_ft=63,
        length_in=0,
        is_visible=True,
    )

    reasons = classify_vinted_cleanup_reasons(ad)

    assert reasons == ["invalid_length_without_support"]


def test_cleanup_vinted_ads_hides_matches_and_clears_board_metrics():
    suspicious = Ad(
        id=1,
        source="vinted",
        model="Surfboard Keychain",
        price=5.0,
        length_ft=5,
        length_in=0,
        is_visible=True,
        link="https://example.com/bad",
    )
    valid = Ad(
        id=2,
        source="vinted",
        model="Torq Surfboard 6'10 46L",
        price=400.0,
        length_ft=6,
        length_in=10,
        liters=46.0,
        is_visible=True,
        link="https://example.com/good",
    )

    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [suspicious, valid]

    summary = cleanup_vinted_ads(mock_db, dry_run=False, service_logger=MagicMock())

    assert summary["scanned_ads"] == 2
    assert summary["hidden_ads"] == 1
    assert summary["price_like_matches"] == 1
    assert summary["obvious_non_board_matches"] == 1
    assert summary["invalid_length_matches"] == 0
    assert suspicious.is_visible is False
    assert suspicious.length_ft is None
    assert suspicious.length_in is None
    assert suspicious.width_in is None
    assert suspicious.thickness_in is None
    assert suspicious.liters is None
    assert valid.is_visible is True
    mock_db.commit.assert_called_once()


def test_cleanup_vinted_ads_dry_run_does_not_mutate_or_commit():
    suspicious = Ad(
        id=1,
        source="vinted",
        model="Surfboard Keychain",
        price=5.0,
        length_ft=5,
        length_in=0,
        is_visible=True,
        link="https://example.com/bad",
    )

    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [suspicious]

    summary = cleanup_vinted_ads(mock_db, dry_run=True, service_logger=MagicMock())

    assert summary["hidden_ads"] == 1
    assert summary["invalid_length_matches"] == 0
    assert suspicious.is_visible is True
    assert suspicious.length_ft == 5
    mock_db.commit.assert_not_called()
