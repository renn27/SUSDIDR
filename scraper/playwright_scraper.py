import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from config.settings import settings
from utils.logger import setup_logger
from scraper.bs4_scraper import SelectorNotFoundException

logger = setup_logger("playwright_scraper")


class PlaywrightScraper:
    """
    Scraper dinamis menggunakan Playwright headless browser (Lazy-loaded).
    Digunakan sebagai fallback otomatis jika static scraping dengan BS4 gagal.
    """

    def __init__(self, url: Optional[str] = None, timeout: Optional[int] = None):
        self.url = url or settings.SCRAPE_URL
        self.timeout_ms = (timeout or settings.REQUEST_TIMEOUT_SECONDS) * 1000
        self._playwright = None
        self._browser = None
        self._context = None

    def _ensure_browser(self):
        """Memastikan instance browser Playwright sudah siap digunakan secara lazy."""
        if self._playwright is None:
            try:
                from playwright.sync_api import sync_playwright
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-gpu"
                    ]
                )
                self._context = self._browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                    locale="en-US"
                )
            except Exception as e:
                logger.warning(f"[Playwright] Browser engine tidak tersedia di environment ini: {e}")
                raise e

    def _clean_price(self, raw_price_text: str) -> float:
        clean_text = raw_price_text.replace(",", "").strip()
        match = re.search(r"(\d+(?:\.\d+)?)", clean_text)
        if not match:
            raise ValueError(f"Gagal konversi harga '{raw_price_text}' ke float")
        return float(match.group(1))

    def _clean_change_percent(self, raw_change_text: str) -> float:
        clean_text = raw_change_text.replace("%", "").replace(",", "").strip()
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", clean_text)
        if not match:
            raise ValueError(f"Gagal konversi persentase '{raw_change_text}' ke float")
        return float(match.group(1))

    def fetch_data(self) -> Dict[str, Any]:
        self._ensure_browser()
        page = self._context.new_page()

        try:
            page.goto(self.url, timeout=self.timeout_ms, wait_until="domcontentloaded")

            price_selectors = [
                'div.N6SYTe span[jsname="Pdsbrc"]',
                'div.N6SYTe',
                'div.YMlKec.fxKbKc',
                'div.AHmHk div.YMlKec',
                'span[jsname="Pdsbrc"]',
            ]

            price_text = None
            for sel in price_selectors:
                try:
                    elem = page.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", text):
                            price_text = text
                            break
                except Exception:
                    continue

            if not price_text:
                raise SelectorNotFoundException("[Playwright] Selector harga tidak ditemukan di halaman!")

            price = self._clean_price(price_text)

            change_selectors = [
                'div.DAicsd span[jsname="vY9t3b"]',
                'div.DAicsd span.ymyBi',
                'div.DAicsd',
                'div.JwB6zf',
                'span[jsname="vY9t3b"]',
            ]

            change_percent = 0.0
            for sel in change_selectors:
                try:
                    elem = page.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if "%" in text:
                            change_percent = self._clean_change_percent(text)
                            break
                except Exception:
                    continue

            return {
                "pair": settings.PAIR_NAME,
                "price": price,
                "change_percent": change_percent,
                "timestamp": datetime.now(timezone.utc),
                "source": "playwright"
            }

        finally:
            page.close()

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
