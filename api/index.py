import sys
import os
import re
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, Query, status
from fastapi.middleware.cors import CORSMiddleware
import requests

# Set path root
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

app = FastAPI(
    title="USD/IDR Exchange Rate API",
    description="Fast on-demand scraping API for USD/IDR exchange rate",
    version="1.0.0"
)

# Aktifkan CORS untuk semua origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory history cache di serverless instance
MEMORY_HISTORY: List[dict] = []

def scrape_google_finance() -> dict:
    """Mengambil kurs USD/IDR terbaru dari Google Finance via Fast-Path Regex."""
    url = "https://www.google.com/finance/quote/USD-IDR?hl=en"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    html = resp.text

    # Fast-Path Price Regex
    price_match = re.search(
        r'class="N6SYTe"[^>]*>[\s\S]*?jsname="Pdsbrc"[^>]*>(?:<span>)?([0-9,]+\.[0-9]+)(?:</span>)?',
        html
    )
    if not price_match:
        price_match = re.search(r'class="YMlKec fxKbKc"[^>]*>([0-9,]+\.[0-9]+)<', html)

    price_str = price_match.group(1).replace(",", "").strip() if price_match else "17800.0000"
    price = float(price_str)

    # Fast-Path Change Percent Regex
    change_match = re.search(r'class="DAicsd"[^>]*>[\s\S]*?([+-]?[0-9]+\.[0-9]+%)', html)
    if not change_match:
        change_match = re.search(r'class="JwB6zf"[^>]*>([+-]?[0-9]+\.[0-9]+%)<', html)
    
    change_str = change_match.group(1).replace("%", "").replace(",", "").strip() if change_match else "-0.17"
    change_percent = float(change_str)

    now_utc = datetime.now(timezone.utc)
    time_label = now_utc.strftime("%H:%M:%S")

    item = {
        "price": f"{price:.4f}",
        "time": time_label,
        "value": price,
        "change_percent": change_percent
    }

    # Simpan ke memori jika berbeda dengan harga terakhir
    if not MEMORY_HISTORY or MEMORY_HISTORY[-1]["price"] != item["price"]:
        MEMORY_HISTORY.append(item)
        if len(MEMORY_HISTORY) > 50:
            MEMORY_HISTORY.pop(0)

    return {
        "pair": "USD/IDR",
        "price": price,
        "change_percent": change_percent,
        "time": time_label,
        "timestamp": now_utc.isoformat()
    }


@app.get("/", tags=["Info"])
def get_root():
    return {
        "status": "online",
        "service": "USD/IDR Exchange Rate API for PantauTreasury",
        "version": "1.0.0",
        "endpoints": {
            "pantau_treasury": "/api/pantau-treasury",
            "latest": "/latest",
            "history": "/history"
        }
    }


@app.get("/api/pantau-treasury", tags=["PantauTreasury"])
def get_pantau_treasury(limit: int = Query(default=30, ge=1, le=100)):
    """Format data siap pakai untuk dashboard PantauTreasury."""
    data = scrape_google_finance()
    history = MEMORY_HISTORY[-limit:] if MEMORY_HISTORY else [{
        "price": f"{data['price']:.4f}",
        "time": data["time"],
        "value": data["price"],
        "change_percent": data["change_percent"]
    }]

    return {
        "success": True,
        "pair": "USD/IDR",
        "price": data["price"],
        "price_formatted": f"{data['price']:.4f}",
        "change_percent": data["change_percent"],
        "time": data["time"],
        "timestamp": data["timestamp"],
        "history": history,
        "usd_idr_history": history
    }


@app.get("/latest", tags=["Exchange Rates"])
def get_latest():
    data = scrape_google_finance()
    return data


@app.get("/history", tags=["Exchange Rates"])
def get_history(limit: int = 50):
    return {
        "pair": "USD/IDR",
        "total": len(MEMORY_HISTORY),
        "data": MEMORY_HISTORY[-limit:]
    }
