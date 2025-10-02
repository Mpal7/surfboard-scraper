from unittest.mock import MagicMock, call
import httpx
from scraper import scrape_and_store, Ad

# It's better to define mock responses once, outside the test functions
# This avoids redefining them in every test
mock_response_search = httpx.Response(
    200,
    html="""
    <html><body>
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
    </body></html>
    """
)

mock_response_detail_valid = httpx.Response(
    200,
    html="""
    <html><body>
        <p class="description">
            Vendo tavola Firewire Seaside, misure 5'11" x 21" x 2 1/2".
            Volume 35 litri. Condizioni ottime.
        </p>
    </body></html>
    """
)

# This response will be for any page we don't care about, to stop loops gracefully.
mock_response_empty = httpx.Response(200, html="<html></html>")

def test_scrape_and_store_happy_path(mocker):
    # 1. Setup Mocks
    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = [("https://www.subito.it/sport/already-in-db-3.htm",)]
    
    # We create a "router" function for side_effect. This is more robust than a list.
    # It returns a specific response based on the URL requested.
    def mock_get_router(url, **kwargs):
        if "valid-surfboard-ad-1.htm" in url:
            return mock_response_detail_valid
        # This is the first search page the scraper will hit
        elif "roma/?q=tavola+da+surf&o=1" in url:
            return mock_response_search
        # For any other URL (like page 2, or other cities), return an empty page.
        # This gracefully stops the scraper's loops.
        else:
            return mock_response_empty

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.side_effect = mock_get_router
    
    mocker.patch('scraper.httpx.Client', return_value=mock_client)
    mocker.patch('scraper.time.sleep')

    # 2. Execute the function
    ads_added = scrape_and_store(mock_db)

    # 3. Assertions
    # Check that we didn't call the detail page for the ad that was skipped by title
    for mock_call in mock_client.get.call_args_list:
        url = mock_call.args[0]
        assert "ad-to-be-skipped-2.htm" not in url
    
    assert len(ads_added) == 1
    mock_db.add.assert_called_once()
    
    added_ad_instance = mock_db.add.call_args[0][0]
    assert isinstance(added_ad_instance, Ad)
    assert added_ad_instance.link == "https://www.subito.it/sport/valid-surfboard-ad-1.htm"
    assert added_ad_instance.brand == "Firewire"
    assert added_ad_instance.price == 450.0
    assert added_ad_instance.length_ft == 5
    assert added_ad_instance.length_in == 11
    assert added_ad_instance.liters == 35.0

    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()

def test_scrape_and_store_access_denied(mocker):
    # 1. Setup Mocks
    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []
    
    # We will patch the search_configs to limit the scope of the test.
    # This prevents the scraper from looping 50 times.
    mocker.patch('scraper.search_configs', [('roma', 'lazio', 'tavola+da+surf')])
    
    access_denied_html = "<html><body><h1>Access Denied</h1></body></html>"
    mock_response_denied = httpx.Response(200, html=access_denied_html)
    
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_response_denied
    
    mocker.patch('scraper.httpx.Client', return_value=mock_client)
    mocker.patch('scraper.time.sleep')

    # 2. Execute
    ads_added = scrape_and_store(mock_db)
    
    # 3. Assertions
    # Now that we've limited the search_configs, this will be called only once.
    assert len(ads_added) == 0
    mock_client.get.assert_called_once()
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()

def test_scrape_and_store_http_error(mocker):
    # 1. Setup Mocks
    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []
    
    # Also limit the scope here for a faster, more focused test.
    mocker.patch('scraper.search_configs', [('roma', 'lazio', 'tavola+da+surf')])
    
    mock_response_error = httpx.Response(500, html="Internal Server Error")
    
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_response_error
    
    mocker.patch('scraper.httpx.Client', return_value=mock_client)
    mocker.patch('scraper.time.sleep')

    # 2. Execute
    ads_added = scrape_and_store(mock_db)

    # 3. Assertions
    assert len(ads_added) == 0
    # It should have tried to scrape the one config and its 5 pages
    assert mock_client.get.call_count == 5 
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()