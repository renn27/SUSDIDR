import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError
from config.settings import settings
from utils.logger import setup_logger
from scraper.bs4_scraper import SelectorNotFoundException

logger = setup_logger("playwright_scraper")


class PlaywrightScraper:
    """
    Scraper dinamis menggunakan Playwright headless browser.
    Digunakan sebagai fallback otomatis jika static scraping dengan BS4 gagal
    (misalnya saat konten di-render via client-side JavaScript atau saat ada anti-bot).
    """

    def __init__(self, url: Optional[str] = None, timeout: Optional[int] = None):
        self.url = url or settings.SCRAPE_URL
        self.timeout_ms = (timeout or settings.REQUEST_TIMEOUT_SECONDS) * 1000
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def _ensure_browser(self):
        """Memastikan instance browser Playwright sudah siap digunakan."""
        if self._playwright is None:
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

    def close(self):
        """Menutup browser dan resources Playwright secara bersih."""
        try:
            if self._context:
                self._context.close()
                self._context = None
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            logger.info("[Playwright] Browser instance berhasil ditutup.")
        except Exception as e:
            logger.warning(f"[Playwright] Error saat menutup browser: {e}")

    def fetch_data(self) -> Dict[str, Any]:
        """
        Membuka halaman Google Finance dengan headless browser dan mengambil nilai kurs.
        
        Returns:
            Dict[str, Any]: {
                "pair": "USD/IDR",
                "price": 17803.85,
                "change_percent": -0.17,
                "timestamp": datetime (UTC),
                "source": "playwright"
            }
        """
        self._ensure_browser()
        page = self._context.new_page()

        try:
            logger.info(f"[Playwright] Membuka URL: {self.url}")
            page.goto(self.url, wait_until="domcontentloaded", timeout=self.timeout_ms)

            # Daftar selector prioritas untuk harga
            price_selectors = [
                'div.N6SYTe span[jsname="Pdsbrc"]',
                'div.N6SYTe',
                'div.YMlKec.fxKbKc',
                'div.AHmHk div.YMlKec',
                'span[jsname="Pdsbrc"]',
            ]

            # Tunggu salah satu selector muncul di DOM
            price_text = None
            for sel in price_selectors:
                try:
                    elem = page.wait_for_selector(sel, timeout=3000)
                    if elem:
                        val = elem.inner_text().strip()
                        if re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", val):
                            price_text = val
                            logger.debug(f"[Playwright] Ditemukan selector '{sel}' dengan nilai: '{val}'")
                            break
                except PlaywrightTimeoutError:
                    continue

            if not price_text:
                raise SelectorNotFoundException("[Playwright] Tidak dapat menemukan elemen harga pada halaman yang dirender.")

            # Bersihkan harga
            clean_price_str = price_text.replace(",", "").strip()
            match_price = re.search(r"(\d+(?:\.\d+)?)", clean_price_str)
            if not match_price:
                raise ValueError(f"Gagal parse harga Playwright: {price_text}")
            price = float(match_price.group(1))

            # Ekstraksi persentase perubahan
            change_percent = 0.0
            change_selectors = [
                'div.DAicsd span[jsname="vY9t3b"]',
                'div.DAicsd span.ymyBi',
                'div.DAicsd',
                'div.JwB6zf',
                'span[jsname="vY9t3b"]',
            ]
            for sel in change_selectors:
                try:
                    elem = page.query_selector(sel)
                    if elem:
                        val = elem.inner_text().strip()
                        if "%" in val:
                            clean_change_str = val.replace("%", "").replace(",", "").strip()
                            match_change = re.search(r"([+-]?\d+(?:\.\d+)?)", clean_change_str)
                            if match_change:
                                change_percent = float(match_change.group(1))
                                break
                except Exception:
                    continue

            fetch_timestamp = datetime.now(timezone.utc)

            return {
                "pair": settings.PAIR_NAME,
                "price": price,
                "change_percent": change_percent,
                "timestamp": fetch_timestamp,
                "source": "playwright"
            }

        except PlaywrightTimeoutError as e:
            logger.error(f"[Playwright] Timeout saat memuat halaman {self.url}: {e}")
            raise e
        except Exception as e:
            logger.error(f"[Playwright] Terjadi kesalahan saat scraping: {e}")
            raise e
        finally:
            page.close()
