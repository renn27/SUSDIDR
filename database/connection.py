import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from utils.logger import setup_logger
from database.models import Base

logger = setup_logger("database")

# Pastikan folder lokal untuk SQLite dibuat jika menggunakan SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )

    # Aktifkan WAL (Write-Ahead Logging) & Timeout untuk konkurensi tinggi tanpa lock
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

else:
    # PostgreSQL / MySQL / lainnya untuk produksi skala besar
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Inisialisasi tabel database (membuat semua tabel yang didefinisikan dalam Base jika belum ada).
    """
    try:
        logger.info(f"Menginisialisasi tabel database dengan URL: {settings.DATABASE_URL}")
        Base.metadata.create_all(bind=engine)
        logger.info("Inisialisasi database berhasil.")
    except Exception as e:
        logger.error(f"Gagal menginisialisasi database: {e}", exc_info=True)
        raise e


def get_db() -> Generator[Session, None, None]:
    """
    Dependency generator untuk FastAPI session management atau context manager.
    Memastikan session ditutup setelah request/operasi selesai.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
