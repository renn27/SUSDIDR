import asyncio
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional, Set
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from config.settings import settings
from utils.logger import setup_logger
from database.connection import init_db, get_db, SessionLocal
from database.crud import get_latest_rate, get_rate_history, save_rate_if_changed
from scraper.poller import CurrencyPoller
from api.schemas import (
    ExchangeRateResponse,
    ExchangeRateHistoryResponse,
    ExchangeRateHistoryItem,
    HealthResponse
)

logger = setup_logger("api", "api.log")

# ==============================================================================
# WebSocket Connection Manager (Untuk Live Push ke PantauTreasury)
# ==============================================================================
class ConnectionManager:
    """Mengelola koneksi WebSocket aktif untuk broadcast data live kurs."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"[WebSocket] Client terhubung. Total client aktif: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"[WebSocket] Client terputus. Sisa client aktif: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Kirim pesan JSON ke seluruh client yang terhubung."""
        if not self.active_connections:
            return
        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        for dead in dead_connections:
            self.active_connections.discard(dead)

    def broadcast_from_thread(self, message: dict):
        """Thread-safe trigger broadcast dari background poller thread."""
        if self.loop and self.loop.is_running() and self.active_connections:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)


ws_manager = ConnectionManager()
poller_instance: Optional[CurrencyPoller] = None
poller_thread: Optional[threading.Thread] = None


# ==============================================================================
# Lifespan Handler (Inisialisasi Database + Background Poller Thread)
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler.
    Jika RUN_POLLER_IN_APP=True, scraper akan berjalan otomatis di background thread.
    Memungkinkan deployment 100% GRATIS di 1 web service (Render / Koyeb / Railway).
    """
    global poller_instance, poller_thread

    logger.info("=" * 60)
    logger.info("🚀 Memulai FastAPI Server untuk USD/IDR Exchange Rate API")
    logger.info(f"CORS Allowed Origins: {settings.cors_origins_list}")
    logger.info(f"Database URL: {settings.DATABASE_URL}")
    logger.info(f"Single-Process Poller Enabled: {settings.RUN_POLLER_IN_APP}")
    logger.info("=" * 60)

    # Inisialisasi database schema
    init_db()

    # Simpan event loop untuk WebSocket broadcast
    try:
        current_loop = asyncio.get_running_loop()
        ws_manager.set_loop(current_loop)
    except RuntimeError:
        pass

    # Jalankan background poller jika diaktifkan
    if settings.RUN_POLLER_IN_APP:
        logger.info("[Background Worker] Menjalankan poller scraper di background thread...")
        poller_instance = CurrencyPoller()
        
        # Patch poller agar memicu broadcast websocket saat ada data baru
        def poll_and_notify():
            data = poller_instance.fetch_exchange_rate()
            if not data:
                return False
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
                    # Ambil riwayat terbaru untuk disiarkan ke PantauTreasury
                    records, _ = get_rate_history(db, pair=data["pair"], limit=30, offset=0)
                    history_items = [
                        {
                            "price": f"{rec.price:.4f}",
                            "time": rec.timestamp.strftime("%H:%M:%S"),
                            "value": rec.price,
                            "change_percent": rec.change_percent
                        }
                        for rec in reversed(records)
                    ]

                    time_label = data["timestamp"].strftime("%H:%M:%S")
                    ws_manager.broadcast_from_thread({
                        "type": "USD_IDR_UPDATE",
                        "pair": data["pair"],
                        "price": data["price"],
                        "change_percent": data["change_percent"],
                        "time": time_label,
                        "timestamp": data["timestamp"].isoformat(),
                        "usd_idr_history": history_items,
                        "source": data.get("source", "bs4")
                    })
                return True
            except Exception as e:
                logger.error(f"[Poller] Error saat menyimpan/broadcast: {e}")
                return False
            finally:
                db.close()

        poller_instance.poll_once = poll_and_notify

        def run_poller_loop():
            poller_instance.start()

        poller_thread = threading.Thread(target=run_poller_loop, daemon=True)
        poller_thread.start()

    yield

    logger.info("🛑 Mematikan FastAPI Server dan Scraper Worker...")
    if poller_instance:
        poller_instance.stop()
        poller_instance.cleanup()


# Inisialisasi FastAPI App
app = FastAPI(
    title="USD/IDR Real-Time Exchange Rate & WebSocket API",
    description=(
        "REST & WebSocket API near real-time untuk kurs USD/IDR dari Google Finance "
        "yang kompatibel langsung dengan dashboard PantauTreasury."
    ),
    version="1.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Konfigurasi Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Endpoint REST API
# ==============================================================================
@app.get("/", tags=["Info"])
def get_root():
    """Endpoint root dengan informasi dasar dan endpoint yang tersedia."""
    return {
        "service": "USD/IDR Real-Time API for PantauTreasury",
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "latest": "/latest",
            "history": "/history?limit=50&offset=0",
            "pantau_treasury": "/api/pantau-treasury",
            "open_er_compatible": "/v6/latest/USD",
            "websocket": "/ws",
            "health": "/health"
        }
    }


@app.get(
    "/latest",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Exchange Rates"],
    summary="Ambil data kurs USD/IDR terbaru"
)
def get_latest(
    pair: str = Query(default=settings.PAIR_NAME, description="Pasangan mata uang, default: USD/IDR"),
    db: Session = Depends(get_db)
):
    """Mengembalikan data kurs terbaru dari database."""
    latest = get_latest_rate(db, pair=pair)
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Belum ada data kurs untuk '{pair}'. Scraper sedang mengumpulkan data awal."
        )

    return ExchangeRateResponse(
        pair=latest.pair,
        price=latest.price,
        change_percent=latest.change_percent,
        timestamp=latest.timestamp
    )


@app.get(
    "/history",
    response_model=ExchangeRateHistoryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Exchange Rates"],
    summary="Ambil riwayat perubahan kurs dengan pagination"
)
def get_history(
    pair: str = Query(default=settings.PAIR_NAME, description="Pasangan mata uang"),
    limit: int = Query(default=50, ge=1, le=1000, description="Jumlah record per halaman"),
    offset: int = Query(default=0, ge=0, description="Offset pagination"),
    db: Session = Depends(get_db)
):
    """Mengembalikan daftar riwayat perubahan kurs."""
    records, total = get_rate_history(db, pair=pair, limit=limit, offset=offset)

    items = [
        ExchangeRateHistoryItem(
            id=rec.id,
            pair=rec.pair,
            price=rec.price,
            change_percent=rec.change_percent,
            timestamp=rec.timestamp
        )
        for rec in records
    ]

    return ExchangeRateHistoryResponse(
        pair=pair,
        total=total,
        limit=limit,
        offset=offset,
        data=items
    )


@app.get(
    "/api/pantau-treasury",
    tags=["PantauTreasury Integration"],
    summary="Format khusus untuk konsumsi langsung dashboard PantauTreasury"
)
def get_pantau_treasury_data(
    limit: int = Query(default=30, ge=1, le=100, description="Jumlah riwayat terakhir"),
    db: Session = Depends(get_db)
):
    """
    Endpoint yang mengembalikan struktur data yang langsung siap dipakai oleh script.js PantauTreasury:
    - rate: Nilai harga saat ini (string & float)
    - change: Persentase perubahan
    - time: Format jam HH:MM:SS
    - history: Array [{ price, time, value }] untuk dropdown riwayat kurs
    """
    latest = get_latest_rate(db, pair=settings.PAIR_NAME)
    if not latest:
        try:
            from scraper.bs4_scraper import BS4Scraper
            scraper = BS4Scraper()
            scraped = scraper.fetch_data()
            latest, _ = save_rate_if_changed(
                db=db,
                pair=scraped["pair"],
                price=scraped["price"],
                change_percent=scraped["change_percent"],
                timestamp=scraped["timestamp"]
            )
        except Exception as e:
            logger.warning(f"On-demand scraper fallback: {e}")

    records, _ = get_rate_history(db, pair=settings.PAIR_NAME, limit=limit, offset=0)

    # Susun riwayat dari terlama ke terbaru (sesuai format state.usdIdrHistory)
    history_items = []
    for rec in reversed(records):
        time_label = rec.timestamp.strftime("%H:%M:%S")
        history_items.append({
            "price": f"{rec.price:.4f}",
            "time": time_label,
            "value": rec.price,
            "change_percent": rec.change_percent
        })

    if not latest:
        return {
            "success": False,
            "message": "Menunggu scraper mengumpulkan data...",
            "latest": None,
            "history": []
        }

    latest_time_label = latest.timestamp.strftime("%H:%M:%S")

    return {
        "success": True,
        "pair": latest.pair,
        "price": latest.price,
        "price_formatted": f"{latest.price:.4f}",
        "change_percent": latest.change_percent,
        "time": latest_time_label,
        "timestamp": latest.timestamp.isoformat(),
        "history": history_items,
        "usd_idr_history": history_items
    }


@app.get(
    "/v6/latest/USD",
    tags=["PantauTreasury Integration"],
    summary="Drop-in mock endpoint kompatibel open.er-api.com"
)
def get_open_er_api_mock(db: Session = Depends(get_db)):
    """
    Endpoint kompatibel 1-ke-1 dengan struktur open.er-api.com.
    Pengguna cukup mengganti konstanta USD_IDR_API_URL di PantauTreasury tanpa ubah kode parsing!
    """
    latest = get_latest_rate(db, pair=settings.PAIR_NAME)
    price = latest.price if latest else 17800.0

    return {
        "result": "success",
        "provider": "Google Finance Real-Time Scraper",
        "base_code": "USD",
        "rates": {
            "IDR": price
        },
        "time_last_update_utc": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "time_next_update_utc": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    }


# ==============================================================================
# WebSocket Endpoint (Live Streaming Push ke PantauTreasury)
# ==============================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    WebSocket endpoint versi mandiri (Self-Hosted) untuk PantauTreasury.
    - Tidak butuh tiket / Cloudflare Turnstile token
    - Tidak butuh auth challenge
    - Mengirim initial snapshot dan broadcast data live setiap ada perubahan harga dari Google Finance!
    """
    await ws_manager.connect(websocket)
    try:
        # Kirim payload inisial saat client pertama kali tersambung
        latest = get_latest_rate(db, pair=settings.PAIR_NAME)
        records, _ = get_rate_history(db, pair=settings.PAIR_NAME, limit=30, offset=0)
        
        history_items = []
        for rec in reversed(records):
            history_items.append({
                "price": f"{rec.price:.4f}",
                "time": rec.timestamp.strftime("%H:%M:%S"),
                "value": rec.price,
                "change_percent": rec.change_percent
            })

        initial_payload = {
            "type": "INITIAL_DATA",
            "pair": settings.PAIR_NAME,
            "price": latest.price if latest else 0.0,
            "change_percent": latest.change_percent if latest else 0.0,
            "time": latest.timestamp.strftime("%H:%M:%S") if latest else "",
            "history": history_items,
            "usd_idr_history": history_items
        }
        await websocket.send_json(initial_payload)

        # Loop mempertahankan koneksi dan merespons ping
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"[WebSocket] Error client: {e}")
        ws_manager.disconnect(websocket)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check API dan koneksi database"
)
def get_health(db: Session = Depends(get_db)):
    """Endpoint health check untuk memantau status aplikasi dan database."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check failed on database ping: {e}")
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        version="1.2.0"
    )
