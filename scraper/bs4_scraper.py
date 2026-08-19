import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from config.settings import settings, WIB
from utils.logger import setup_logger

logger = setup_logger("bs4_scraper")


class ScraperException(Exception):
    """Base exception class for scraping errors."""
    pass


class SelectorNotFoundException(ScraperException):
    """Raised when expected HTML elements/selectors are not found."""
    pass


class BS4Scraper:
    """
    Scraper statis ultra-cepat menggunakan connection pooling, HTTP compression,
    dan Fast-Path Regex parsing sebelum fallback ke BeautifulSoup4.
    """

    def __init__(self, url: Optional[str] = None, timeout: Optional[int] = None):
        self.url = url or settings.SCRAPE_URL
        self.timeout = timeout or settings.REQUEST_TIMEOUT_SECONDS
        
        # Konfigurasi Session dengan Connection Pooling & Keep-Alive
        self.session = requests.Session()
        retries = Retry(
            total=2,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=retries
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Header standar browser modern dengan HTTP Compression (gzip/br)
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        })

    def _clean_price(self, raw_price_text: str) -> float:
        """Membersihkan string harga menjadi float (contoh: '17,803.8500' -> 17803.85)."""
        clean_text = raw_price_text.replace(",", "").strip()
        match = re.search(r"(\d+(?:\.\d+)?)", clean_text)
        if not match:
            raise ValueError(f"Tidak dapat mengonversi string harga '{raw_price_text}' ke float")
        return float(match.group(1))

    def _clean_change_percent(self, raw_change_text: str) -> float:
        """Membersihkan string persentase perubahan menjadi float (contoh: '-0.17%' -> -0.17)."""
        clean_text = raw_change_text.replace("%", "").replace(",", "").strip()
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", clean_text)
        if not match:
            raise ValueError(f"Tidak dapat mengonversi persentase perubahan '{raw_change_text}' ke float")
        return float(match.group(1))

    def fetch_data(self) -> Dict[str, Any]:
        """
        Mengambil HTML dari Google Finance dan mengekstrak data kurs USD/IDR.
        Menggunakan Fast-Path Regex terlebih dahulu untuk performa < 0.2ms,
        lalu fallback ke BeautifulSoup jika struktur berubah.
        """
        try:
            response = self.session.get(self.url, timeout=self.timeout)
            response.raise_for_status()
        except requests.Timeout as e:
            logger.error(f"[BS4] Request timeout setelah {self.timeout} detik ke {self.url}")
            raise e
        except requests.RequestException as e:
            logger.error(f"[BS4] Request HTTP error: {e}")
            raise e

        html_text = response.text

        # =========================================================================
        # FAST-PATH REGEX: Ekstraksi langsung tanpa overhead parsing tree 1MB HTML
        # =========================================================================
        price = None
        change_percent = 0.0

        # Pattern harga quote utama Google Finance
        # Contoh: class="N6SYTe" ... jsname="Pdsbrc"><span>17,803.8500</span>
        fast_price_match = re.search(
            r'class="N6SYTe"[^>]*>[\s\S]*?jsname="Pdsbrc"[^>]*>(?:<span>)?([0-9,]+\.[0-9]+)(?:</span>)?',
            html_text
        )
        if not fast_price_match:
            # Pola alternatif YMlKec fxKbKc
            fast_price_match = re.search(
                r'class="YMlKec fxKbKc"[^>]*>([0-9,]+\.[0-9]+)<',
                html_text
            )

        # Pattern persentase perubahan quote utama (DAicsd adalah container spesifik quote utama)
        fast_change_match = re.search(
            r'class="DAicsd"[^>]*>[\s\S]*?([+-]?[0-9]+\.[0-9]+%)',
            html_text
        )
        if not fast_change_match:
            fast_change_match = re.search(
                r'class="JwB6zf"[^>]*>([+-]?[0-9]+\.[0-9]+%)<',
                html_text
            )
        if not fast_change_match:
            fast_change_match = re.search(
                r'jsname="vY9t3b"[^>]*>[\s\S]*?([+-]?[0-9]+\.[0-9]+%)',
                html_text
            )

        if fast_price_match:
            try:
                price = self._clean_price(fast_price_match.group(1))
                if fast_change_match:
                    change_percent = self._clean_change_percent(fast_change_match.group(1))
                
                return {
                    "pair": settings.PAIR_NAME,
                    "price": price,
                    "change_percent": change_percent,
                    "timestamp": settings.get_wib_now() if hasattr(settings, "get_wib_now") else datetime.now(timezone(timedelta(hours=7))),
                    "source": "bs4-fastpath"
                }
            except Exception:
                pass # Lanjut ke full DOM fallback jika fast-path gagal

        # =========================================================================
        # FULL DOM FALLBACK: BeautifulSoup parsing komprehensif
        # =========================================================================
        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Ekstraksi Harga Utama
        price_elem = None
        price_selectors = [
            'div.N6SYTe span[jsname="Pdsbrc"]',
            'div.N6SYTe',
            'div.YMlKec.fxKbKc',
            'div.AHmHk div.YMlKec',
            'div[data-last-price]',
            'span[jsname="Pdsbrc"]',
        ]

        for selector in price_selectors:
            found = soup.select_one(selector)
            if found and found.get_text(strip=True):
                text = found.get_text(strip=True)
                if re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", text):
                    price_elem = found
                    break

        if not price_elem:
            container = soup.find(string=re.compile(r"United States Dollar / Indonesian Rupiah|USD / IDR"))
            if container:
                parent = container.find_parent("div")
                if parent:
                    number_match = parent.find_next(string=re.compile(r"^\d{1,3}(?:,\d{3})+(?:\.\d+)?$"))
                    if number_match:
                        price_elem = number_match

        if not price_elem:
            err_msg = "[BS4] Selector harga tidak ditemukan pada HTML Google Finance!"
            logger.warning(err_msg)
            raise SelectorNotFoundException(err_msg)

        price = self._clean_price(price_elem.get_text(strip=True))

        # 2. Ekstraksi Persentase Perubahan
        change_elem = None
        change_selectors = [
            'div.DAicsd span[jsname="vY9t3b"]',
            'div.DAicsd span.ymyBi',
            'div.DAicsd',
            'div.JwB6zf',
            'span[jsname="vY9t3b"]',
        ]

        for selector in change_selectors:
            found = soup.select_one(selector)
            if found and "%" in found.get_text():
                change_elem = found
                break

        if change_elem:
            change_percent = self._clean_change_percent(change_elem.get_text(strip=True))

        return {
            "pair": settings.PAIR_NAME,
            "price": price,
            "change_percent": change_percent,
            "timestamp": datetime.now(timezone(timedelta(hours=7))),
            "source": "bs4"
        }
