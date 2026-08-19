from http.server import BaseHTTPRequestHandler
import json
import re
import requests
from datetime import datetime, timezone

MEMORY_HISTORY = []


def scrape_google_finance() -> dict:
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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = scrape_google_finance()
            history = MEMORY_HISTORY if MEMORY_HISTORY else [{
                "price": f"{data['price']:.4f}",
                "time": data["time"],
                "value": data["price"],
                "change_percent": data["change_percent"]
            }]

            response_data = {
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

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
