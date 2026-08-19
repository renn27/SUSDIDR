import pytest
from scraper.bs4_scraper import BS4Scraper, SelectorNotFoundException
from unittest.mock import patch, MagicMock


def test_clean_price_and_percent():
    scraper = BS4Scraper()
    assert scraper._clean_price("17,798.9500") == 17798.95
    assert scraper._clean_price("15,750.25") == 15750.25
    assert scraper._clean_price("16000") == 16000.0

    assert scraper._clean_change_percent("+0.12%") == 0.12
    assert scraper._clean_change_percent("-0.20%") == -0.20
    assert scraper._clean_change_percent("0.00%") == 0.0


def test_bs4_scraper_success_with_sample_html():
    sample_html = """
    <html>
        <body>
            <div class="gO24Ff">United States Dollar / Indonesian Rupiah</div>
            <div class="N6SYTe">
                <span jsname="Pdsbrc"><span>17,800.50</span></span>
            </div>
            <span jsname="vY9t3b"><span>+0.25%</span></span>
        </body>
    </html>
    """
    scraper = BS4Scraper()

    with patch.object(scraper.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        data = scraper.fetch_data()

        assert data["pair"] == "USD/IDR"
        assert data["price"] == 17800.50
        assert data["change_percent"] == 0.25
        assert data["source"] in ["bs4", "bs4-fastpath"]
        assert data["timestamp"] is not None


def test_bs4_scraper_alternative_selector_success():
    sample_html = """
    <html>
        <body>
            <div class="YMlKec fxKbKc">16,250.75</div>
            <div class="JwB6zf">-0.15%</div>
        </body>
    </html>
    """
    scraper = BS4Scraper()

    with patch.object(scraper.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        data = scraper.fetch_data()

        assert data["price"] == 16250.75
        assert data["change_percent"] == -0.15


def test_bs4_scraper_missing_selector_raises_exception():
    invalid_html = "<html><body><div>Halaman Tidak Dikenali</div></body></html>"
    scraper = BS4Scraper()

    with patch.object(scraper.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = invalid_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(SelectorNotFoundException):
            scraper.fetch_data()
