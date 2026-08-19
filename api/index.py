from http.server import BaseHTTPRequestHandler
import json
import re
import requests
from datetime import datetime, timezone

# Cache in-memory untuk menyimpan data dan riwayat kurs
LAST_DATA = {
    "price": 17800.0,
    "change_percent": -0.17,
    "time": "12:00:00",
    "timestamp": datetime.now(timezone.utc).isoformat()
}
MEMORY_HISTORY = []


def fetch_usd_idr_rate() -> dict:
    """
    Mengambil data kurs USD/IDR dengan sistem multi-tier:
    1. Google Finance (Scraping Fast-Path)
    2. Fallback: Open Exchange Rate API (Jika Google timeout/block)
    3. Fallback: Cache terakhir
    """
    global LAST_DATA, MEMORY_HISTORY

    # 1. Coba Scraping Google Finance
    try:
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
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            html = resp.text
            price_match = re.search(
                r'class="N6SYTe"[^>]*>[\s\S]*?jsname="Pdsbrc"[^>]*>(?:<span>)?([0-9,]+\.[0-9]+)(?:</span>)?',
                html
            )
            if not price_match:
                price_match = re.search(r'class="YMlKec fxKbKc"[^>]*>([0-9,]+\.[0-9]+)<', html)

            if price_match:
                price = float(price_match.group(1).replace(",", "").strip())
                
                change_match = re.search(r'class="DAicsd"[^>]*>[\s\S]*?([+-]?[0-9]+\.[0-9]+%)', html)
                if not change_match:
                    change_match = re.search(r'class="JwB6zf"[^>]*>([+-]?[0-9]+\.[0-9]+%)<', html)
                
                change_str = change_match.group(1).replace("%", "").replace(",", "").strip() if change_match else "-0.17"
                change_percent = float(change_str)

                now_utc = datetime.now(timezone.utc)
                time_label = now_utc.strftime("%H:%M:%S")

                LAST_DATA = {
                    "price": price,
                    "change_percent": change_percent,
                    "time": time_label,
                    "timestamp": now_utc.isoformat()
                }
                _append_history(price, change_percent, time_label)
                return LAST_DATA
    except Exception:
        pass

    # 2. Fallback: Open Exchange Rates API
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        if resp.status_code == 200:
            json_data = resp.json()
            idr_rate = json_data.get("rates", {}).get("IDR")
            if idr_rate:
                price = round(float(idr_rate), 4)
                now_utc = datetime.now(timezone.utc)
                time_label = now_utc.strftime("%H:%M:%S")

                LAST_DATA = {
                    "price": price,
                    "change_percent": -0.15,
                    "time": time_label,
                    "timestamp": now_utc.isoformat()
                }
                _append_history(price, -0.15, time_label)
                return LAST_DATA
    except Exception:
        pass

    # 3. Fallback: Cache terakhir
    return LAST_DATA


def _append_history(price: float, change_percent: float, time_label: str):
    global MEMORY_HISTORY
    item = {
        "price": f"{price:.4f}",
        "time": time_label,
        "value": price,
        "change_percent": change_percent
    }
    if not MEMORY_HISTORY or MEMORY_HISTORY[-1]["price"] != item["price"]:
        MEMORY_HISTORY.append(item)
        if len(MEMORY_HISTORY) > 50:
            MEMORY_HISTORY.pop(0)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = fetch_usd_idr_rate()
        history = MEMORY_HISTORY if MEMORY_HISTORY else [{
            "price": f"{data['price']:.4f}",
            "time": data["time"],
            "value": data["price"],
            "change_percent": data["change_percent"]
        }]

        response_payload = {
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

        body = json.dumps(response_payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
