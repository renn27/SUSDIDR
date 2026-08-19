import time
import signal
import sys
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config.settings import settings
from utils.logger import setup_logger
from database.connection import init_db, SessionLocal
from database.crud import save_rate_if_changed, get_latest_rate, prune_old_rates
from scraper.bs4_scraper import BS4Scraper, SelectorNotFoundException
from scraper.playwright_scraper import PlaywrightScraper

logger = setup_logger("poller", "scraper.log")


class CurrencyPoller:
    """
    Service background polling untuk mengambil data kurs secara berkala,
    memvalidasi perubahan, dan menyimpannya ke database dengan optimasi efisiensi tinggi.
    """

    def __init__(self):
        self.running = False
        self.bs4_scraper = BS4Scraper()
        self.playwright_scraper: Optional[PlaywrightScraper] = None
        self.consecutive_errors = 0
        self.poll_count = 0

    def _get_playwright_scraper(self) -> PlaywrightScraper:
        """Inisialisasi lazy untuk Playwright scraper agar hemat memory."""
        if self.playwright_scraper is None:
            self.playwright_scraper = PlaywrightScraper()
        return self.playwright_scraper

    def fetch_exchange_rate(self) -> Optional[Dict[str, Any]]:
        """
        Mengambil data kurs dengan prioritas:
        1. Requests + BS4 / Fast-Path Regex (Cepat & Hemat Resource ~ 0.2ms parsing)
        2. Fallback: Playwright Headless Browser jika BS4 gagal/di-render dinamis
        
        Returns:
            Optional[Dict[str, Any]]: Data kurs atau None jika semua metode gagal
        """
        # Step 1: Coba static / fast-path scraping dengan BS4
        try:
            data = self.bs4_scraper.fetch_data()
            self.consecutive_errors = 0 # Reset error streak jika berhasil
            return data
        except SelectorNotFoundException as e:
            logger.warning(f"[Poller] BS4 selector miss: {e}. Mengaktifkan fallback Playwright...")
        except Exception as e:
            logger.warning(f"[Poller] BS4 request gagal ({type(e).__name__}: {e}). Mengaktifkan fallback Playwright...")

        # Step 2: Fallback ke Playwright Headless Browser
        try:
            pw = self._get_playwright_scraper()
            logger.info("[Poller] Menjalankan scraping fallback via Playwright headless...")
            data = pw.fetch_data()
            self.consecutive_errors = 0
            return data
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"[Poller] Fallback Playwright juga gagal ({type(e).__name__}: {e}). Error beruntun: {self.consecutive_errors}")
            return None

    def poll_once(self) -> bool:
        """
        Menjalankan satu siklus pengambilan data dan penyimpanan ke database.
        
        Returns:
            bool: True jika data berhasil didapatkan, False jika gagal.
        """
        self.poll_count += 1
        data = self.fetch_exchange_rate()
        if not data:
            return False

        # Simpan ke database hanya jika nilai kurs berubah
        db = SessionLocal()
        try:
            record, was_saved = save_rate_if_changed(
                db=db,
                pair=data["pair"],
                price=data["price"],
                change_percent=data["change_percent"],
                timestamp=data["timestamp"]
            )
            if was_saved:
                logger.info(
                    f"[DATA BARU DISIMPAN] {data['pair']} = Rp {data['price']:,.2f} "
                    f"({data['change_percent']:+.2f}%) [Source: {data.get('source', 'unknown')}]"
                )
            else:
                logger.debug(
                    f"[KURS TETAP] {data['pair']} = Rp {data['price']:,.2f} [Source: {data.get('source', 'unknown')}]"
                )

            # Lakukan pembersihan database berkala otomatis setiap 500 siklus polling (maks 5.000 data)
            if self.poll_count % 500 == 0:
                pruned = prune_old_rates(db, pair=data["pair"], max_keep=5000)
                if pruned > 0:
                    logger.info(f"[Auto-Prune] Berhasil membersihkan {pruned} record kurs lama dari database.")

            return True
        except Exception as e:
            logger.error(f"[Poller] Kesalahan saat menyimpan ke database: {e}", exc_info=True)
            return False
        finally:
            db.close()

    def start(self):
        """
        Memulai polling loop secara terus-menerus dengan smart interval & backoff.
        """
        logger.info("=" * 60)
        logger.info(f"🚀 Memulai USD/IDR Poller Service")
        logger.info(f"📍 Target URL: {settings.SCRAPE_URL}")
        logger.info(f"⏱  Polling Interval: {settings.POLL_INTERVAL_SECONDS} detik")
        logger.info(f"💾 Database: {settings.DATABASE_URL}")
        logger.info("=" * 60)

        # Inisialisasi database schema & pembersihan awal
        init_db()
        try:
            db_init = SessionLocal()
            prune_old_rates(db_init, pair=settings.PAIR_NAME, max_keep=5000)
            db_init.close()
        except Exception as err:
            logger.warning(f"[Poller] Startup DB maintenance warning: {err}")

        self.running = True

        # Signal handlers untuk graceful shutdown (hanya jika di main thread)
        if threading.current_thread() is threading.main_thread():
            def handle_shutdown(signum, frame):
                logger.info("\n🛑 Menerima sinyal berhenti. Menghentikan poller...")
                self.stop()

            try:
                signal.signal(signal.SIGINT, handle_shutdown)
                signal.signal(signal.SIGTERM, handle_shutdown)
            except (ValueError, AttributeError):
                pass

        # Polling Loop dengan Smart Backoff
        while self.running:
            start_time = time.time()
            try:
                self.poll_once()
            except Exception as e:
                logger.error(f"[Poller] Terjadi error tak terduga dalam loop: {e}", exc_info=True)

            # Hitung waktu tunggu dinamis (Smart Backoff saat koneksi terputus)
            base_interval = settings.POLL_INTERVAL_SECONDS
            if self.consecutive_errors > 0:
                # Exponential backoff hingga max 60s jika internet putus
                backoff = min(60, base_interval * (2 ** min(self.consecutive_errors, 4)))
                logger.warning(f"[Poller] Mode Backoff aktif. Menunggu {backoff} detik sebelum mencoba lagi...")
                target_sleep = backoff
            else:
                elapsed = time.time() - start_time
                target_sleep = max(0.5, base_interval - elapsed)

            # Sleep terpotong agar responsif terhadap sinyal shutdown
            sleep_step = 0.5
            slept = 0.0
            while slept < target_sleep and self.running:
                time.sleep(min(sleep_step, target_sleep - slept))
                slept += sleep_step

        self.cleanup()
        logger.info("Poller service telah dimatikan dengan aman.")

    def stop(self):
        """Menghentikan loop polling."""
        self.running = False

    def cleanup(self):
        """Membersihkan resource browser jika aktif."""
        if self.playwright_scraper:
            self.playwright_scraper.close()


def main():
    """Entry point untuk menjalankan poller service dari CLI/Docker."""
    poller = CurrencyPoller()
    poller.start()


if __name__ == "__main__":
    main()
