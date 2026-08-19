import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from config.settings import settings


def setup_logger(name: str, log_filename: str = None) -> logging.Logger:
    """
    Menyiapkan logger dengan handler console dan file handler rotasi.
    
    Args:
        name (str): Nama logger (misal: 'scraper', 'api', 'database')
        log_filename (str, optional): Nama file log tujuan. Jika None, menggunakan nama logger.
    
    Returns:
        logging.Logger: Instance logger yang sudah terkonfigurasi.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Cegah duplikasi handler jika setup_logger dipanggil berulang kali
    if logger.handlers:
        return logger

    # Format pesan log
    log_format = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler (Output ke terminal dengan UTF-8 fallback safe)
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # 2. File Handler dengan Rotasi Otomatis (Max 5MB per file, simpan 5 backup)
    try:
        os.makedirs(settings.LOG_DIR, exist_ok=True)
        if not log_filename:
            log_filename = f"{name}.log"
        log_path = os.path.join(settings.LOG_DIR, log_filename)

        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Gagal menginisialisasi file logging pada {settings.LOG_DIR}: {e}")

    return logger
