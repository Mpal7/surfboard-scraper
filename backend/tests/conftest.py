import pytest

@pytest.fixture
def mock_search_results_page_html():
    """Provides a mock HTML for a search results page with two ads."""
    return """
    <html>
        <body>
            <div class="item-card">
                <a href="https://www.subito.it/sport/valid-surfboard-ad-1.htm"></a>
                <h2>Tavola da surf 5'11 Firewire - 450€</h2>
                <img src="https://example.com/image1.jpg"/>
                <p>Milano</p>
            </div>
            <div class="item-card">
                <a href="https://www.subito.it/sport/ad-to-be-skipped-2.htm"></a>
                <h2>Sacca per Kitesurf - 50€</h2>
                <img src="https://example.com/image2.jpg"/>
                <p>Milano</p>
            </div>
             <div class="item-card">
                <a href="https://www.subito.it/sport/already-in-db-3.htm"></a>
                <h2>Tavola da surf 6'2 - 300€</h2>
                <img src="https://example.com/image3.jpg"/>
                <p>Milano</p>
            </div>
        </body>
    </html>
    """

@pytest.fixture
def mock_ad_detail_page_html():
    """Provides a mock HTML for a valid ad's detail page."""
    return """
    <html>
        <body>
            <p class="description">
                Vendo tavola Firewire Seaside, misure 5'11" x 21" x 2 1/2".
                Volume 35 litri. Condizioni ottime.
            </p>
        </body>
    </html>
    """

@pytest.fixture
def mock_kitesurf_detail_page_html():
    """Provides a mock HTML for an ad that should be filtered out."""
    return """
    <html>
        <body>
            <p class="description">
                Vendo attrezzatura completa per kitesurf. La tavola è perfetta
                per chi inizia questo sport.
            </p>
        </body>
    </html>
    """