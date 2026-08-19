import os
from datetime import datetime, timezone, timedelta
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Definisi Zona Waktu WIB (Waktu Indonesia Barat / UTC+7)
WIB = timezone(timedelta(hours=7), name="WIB")


def get_wib_now() -> datetime:
    """Mengembalikan objek datetime saat ini dalam zona waktu WIB (UTC+7)."""
    return datetime.now(WIB)


class Settings(BaseSettings):
    """
    Konfigurasi global aplikasi menggunakan Pydantic Settings.
    Nilai-nilai ini dibaca dari environment variable atau file .env.
    """
    # Environment
    ENVIRONMENT: str = Field(default="development", description="Mode environment (development/production)")

    # Database Configuration
    DATABASE_URL: str = Field(
        default="sqlite:////tmp/exchange_rates.db" if os.environ.get("VERCEL") else "sqlite:///./data/exchange_rates.db",
        description="Koneksi database (SQLite default, atau PostgreSQL: postgresql://user:pass@host:5432/dbname)"
    )

    # Scraper Configuration
    SCRAPE_URL: str = Field(
        default="https://www.google.com/finance/quote/USD-IDR?hl=en",
        description="URL Google Finance untuk USD/IDR"
    )
    PAIR_NAME: str = Field(
        default="USD/IDR",
        description="Nama pasangan mata uang"
    )
    POLL_INTERVAL_SECONDS: int = Field(
        default=5,
        description="Interval waktu pengecekan data kurs (dalam detik)"
    )
    REQUEST_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="Timeout untuk HTTP request ke Google Finance (dalam detik)"
    )
    MAX_RETRIES: int = Field(
        default=3,
        description="Jumlah percobaan ulang saat request gagal"
    )
    PLAYWRIGHT_HEADLESS: bool = Field(
        default=True,
        description="Jalankan Playwright dalam mode headless (tanpa GUI browser)"
    )

    # Free Hosting / Single Process Mode
    # Jika True, background poller akan otomatis berjalan di thread background saat FastAPI dinyalakan.
    # Sangat berguna untuk free hosting (Render, Koyeb, Railway) yang hanya menyediakan 1 container gratis!
    RUN_POLLER_IN_APP: bool = Field(
        default=True,
        description="Jalankan poller scraper otomatis di background thread FastAPI (mode single-service)"
    )

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="Host untuk API server")
    API_PORT: int = Field(default=8000, description="Port untuk API server")
    CORS_ALLOWED_ORIGINS: str = Field(
        default="*",
        description="Daftar domain yang diizinkan untuk CORS (pisahkan dengan koma atau * untuk semua)"
    )

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", description="Level logging (DEBUG, INFO, WARNING, ERROR)")
    LOG_DIR: str = Field(default="./logs", description="Direktori penyimpanan file log")

    @property
    def cors_origins_list(self) -> List[str]:
        """Mengembalikan daftar allowed origins dalam bentuk list string."""
        if self.CORS_ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Singleton instance untuk diakses di seluruh aplikasi
settings = Settings()
