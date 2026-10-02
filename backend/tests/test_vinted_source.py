from unittest.mock import MagicMock

import httpx
from bs4 import BeautifulSoup

from src.models import Ad
from src.scraper import scrape_and_store
from src.vinted import extract_detail_description, extract_listings_from_html, strip_price_mentions


VINTED_SEARCH_HTML = """
<html>
  <body>
    <div>
      <img src="https://images1.vinted.net/item-1.jpg" />
      <a
        href="https://www.vinted.it/items/8486358205-tavola-da-surf-firewire?referrer=catalog"
        title="Tavola da surf Firewire, brand: Firewire, condizioni: Buono, €8.00, €9.10 include la Protezione acquisti"
      >
        <div></div>
      </a>
    </div>
  </body>
</html>
"""

VINTED_DETAIL_HTML = """
<html>
  <head>
    <meta
      name="description"
      content="Vendo tavola Firewire in ottime condizioni. Misure 6'4 x 20 1/2 x 2 5/8. Volume 34L."
    />
    <meta property="og:image" content="https://images1.vinted.net/detail-item.jpg" />
  </head>
  <body>
    <p>Vendo tavola Firewire in ottime condizioni. Misure 6'4 x 20 1/2 x 2 5/8. Volume 34L.</p>
  </body>
</html>
"""

VINTED_NON_BOARD_SEARCH_HTML = """
<html>
  <body>
    <div>
      <img src="https://images1.vinted.net/item-2.jpg" />
      <a
        href="https://www.vinted.it/items/1234567890-libro-sul-surf?referrer=catalog"
        title="Libro sul surf vintage, condizioni: Buono, €8.00, €9.10 include la Protezione acquisti"
      >
        <div></div>
      </a>
    </div>
  </body>
</html>
"""

VINTED_NON_BOARD_DETAIL_HTML = """
<html>
  <body>
    <p>Libro fotografico sul surf. Nessuna tavola inclusa.</p>
  </body>
</html>
"""


def _mock_client(router):
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.side_effect = router
    return mock_client


def test_extract_listings_from_vinted_html():
    soup = BeautifulSoup(VINTED_SEARCH_HTML, "html.parser")

    listings = extract_listings_from_html(soup)

    assert len(listings) == 1
    listing = listings[0]
    assert listing["marketplace"] == "vinted"
    assert listing["link"] == "https://www.vinted.it/items/8486358205-tavola-da-surf-firewire"
    assert listing["model"] == "Tavola da surf Firewire"
    assert listing["image_url"] == "https://images1.vinted.net/item-1.jpg"
    assert "€8.00" in listing["full_text"]


def test_strip_price_mentions_removes_euro_tokens():
    assert strip_price_mentions("Tavola 6'4 perfetta € 450,00 trattabili") == (
        "Tavola 6'4 perfetta trattabili"
    )


def test_extract_detail_description_prefers_dimension_rich_candidate():
    soup = BeautifulSoup(VINTED_DETAIL_HTML, "html.parser")

    description = extract_detail_description(soup)

    assert "6'4" in description
    assert "34L" in description


def test_scrape_and_store_ingests_vinted_listing(mocker):
    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []

    def router(url, **kwargs):
        if "/items/" in url:
            return httpx.Response(200, html=VINTED_DETAIL_HTML)
        if "vinted.it/catalog" in url:
            return httpx.Response(200, html=VINTED_SEARCH_HTML)
        return httpx.Response(200, html="<html></html>")

    mock_client = _mock_client(router)
    mocker.patch("src.scraper.httpx.Client", return_value=mock_client)
    mocker.patch("src.scraper.time.sleep")
    mocker.patch("src.scraper.search_configs", [])
    mocker.patch("src.scraper.ENABLE_VINTED_SOURCE", True)
    mocker.patch("src.scraper.VINTED_SEARCH_TERMS", ["tavola da surf"])
    mocker.patch("src.scraper.VINTED_MAX_PAGES_PER_SEARCH", 1)

    ads_added = scrape_and_store(mock_db)

    assert len(ads_added) == 1
    added_ad = mock_db.add.call_args[0][0]
    assert isinstance(added_ad, Ad)
    assert added_ad.source == "vinted"
    assert added_ad.link == "https://www.vinted.it/items/8486358205-tavola-da-surf-firewire"
    assert added_ad.price == 8.0
    assert added_ad.brand == "Firewire"
    assert added_ad.length_ft == 6
    assert added_ad.length_in == 4
    assert added_ad.width_in == 20.5
    assert added_ad.thickness_in == 2.625
    assert added_ad.liters == 34.0
    assert added_ad.image_url == "https://images1.vinted.net/item-1.jpg"
    assert added_ad.is_visible is True
    mock_db.commit.assert_called_once()


def test_scrape_and_store_stores_vinted_false_positive_as_hidden(mocker):
    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []

    def router(url, **kwargs):
        if "/items/" in url:
            return httpx.Response(200, html=VINTED_NON_BOARD_DETAIL_HTML)
        if "vinted.it/catalog" in url:
            return httpx.Response(200, html=VINTED_NON_BOARD_SEARCH_HTML)
        return httpx.Response(200, html="<html></html>")

    mock_client = _mock_client(router)
    mocker.patch("src.scraper.httpx.Client", return_value=mock_client)
    mocker.patch("src.scraper.time.sleep")
    mocker.patch("src.scraper.search_configs", [])
    mocker.patch("src.scraper.ENABLE_VINTED_SOURCE", True)
    mocker.patch("src.scraper.VINTED_SEARCH_TERMS", ["tavola da surf"])
    mocker.patch("src.scraper.VINTED_MAX_PAGES_PER_SEARCH", 1)

    ads_added = scrape_and_store(mock_db)

    assert len(ads_added) == 1
    added_ad = mock_db.add.call_args[0][0]
    assert added_ad.source == "vinted"
    # A false positive is stored for reconciliation but hidden from the UI.
    assert added_ad.is_visible is False
