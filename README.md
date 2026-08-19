# USD/IDR Near Real-Time Scraper & Cloud API 🚀

Aplikasi modular berkinerja tinggi untuk mengambil (*scraping*) kurs mata uang **USD ke IDR** dari Google Finance secara real-time, menyimpannya secara cerdas dengan **deduplikasi** ke database SQLite/PostgreSQL, dan menyediakannya sebagai **FastAPI REST API & WebSocket Server** (untuk lokal/VPS/Docker) serta **Vercel Serverless Function** (untuk cloud 100% gratis 24/7).

---

## 🌟 Arsitektur & Fitur Utama

1. **Scraping Multi-Tier Berkecepatan Tinggi**:
   - **Tier 1 (Fast-Path Regex)**: Ekstraksi langsung dalam < 0.2ms tanpa overhead parsing DOM 1.1 MB.
   - **Tier 2 (BeautifulSoup4)**: Multi-selector DOM fallback otomatis jika struktur berubah.
   - **Tier 3 (Playwright Headless)**: Dynamic JavaScript rendering fallback.
   - **Tier 4 (Open Exchange Rate Fallback)**: Fallback otomatis jika terjadi rate limit / network block.
2. **Deduplikasi Cerdas**:
   - Membandingkan nilai kurs baru dengan data terakhir. Hanya menyimpan record baru jika kurs **berubah**.
3. **Database Maintenance (WAL Mode + Pruning)**:
   - SQLite berjalan dalam mode **WAL (Write-Ahead Logging)** dengan timeout 5s untuk mencegah *database lock*.
   - Otomatis melakukan pruning untuk menjaga maksimal 10.000 record terbaru agar database tetap ringan dan kencang selamanya.
4. **Integrasi Khusus PantauTreasury**:
   - Endpoint `/api/pantau-treasury` (atau `/api/index` di Vercel) yang mengembalikan struktur data lengkap siap pakai.
   - Dropdown riwayat harga terisi penuh secara otomatis.

---

## 📁 Struktur Direktori Project

```text
ScrapingUSDIDR/
├── api/
│   ├── index.js             # Vercel Serverless Function (100% cloud gratis 24/7)
│   ├── main.py              # FastAPI REST API & WebSocket server
│   ├── schemas.py           # Pydantic data validation schemas
│   └── __init__.py
├── config/
│   ├── settings.py          # Environment settings & configuration
│   └── __init__.py
├── database/
│   ├── models.py            # SQLAlchemy ORM models (ExchangeRate)
│   ├── connection.py        # Database engine (WAL Mode & connection pooling)
│   ├── crud.py              # Data access, deduplication, & pruning
│   └── __init__.py
├── scraper/
│   ├── bs4_scraper.py       # Keep-Alive requests + Fast-Path Regex + BS4
│   ├── playwright_scraper.py# Headless browser dynamic fallback (lazy-loaded)
│   ├── poller.py            # Continuous background poller with exponential backoff
│   └── __init__.py
├── tests/                   # Test suite (18 unit & integration tests)
│   ├── test_api.py
│   ├── test_database.py
│   └── test_scraper.py
├── utils/
│   ├── logger.py            # Console & rotating file logger (UTF-8 safe)
│   └── __init__.py
├── Dockerfile               # Production multi-stage Docker container
├── docker-compose.yml       # Multi-service container setup
├── requirements.txt         # Python dependencies
├── .env.example             # Template environment variables
└── README.md                # Dokumentasi lengkap
```

---

## 💻 Cara Menjalankan Secara Lokal

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Jalankan FastAPI Server (otomatis menyalakan background scraper)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Akses dokumentasi interaktif Swagger UI di browser: `http://localhost:8000/docs`.

---

## ☁️ Deployment Cloud 24/7 (Vercel)

1. Push project ini ke repository GitHub Anda (`renn27/SUSDIDR`).
2. Buka [https://vercel.com](https://vercel.com) -> Klik **Add New...** -> **Project** -> Import repo `SUSDIDR`.
3. Klik **Deploy**. Vercel akan otomatis menyalakan serverless endpoint di `https://<project-name>.vercel.app/api/index`.

---

## 🔗 Menghubungkan ke `PantauTreasury`

Di dalam file `PantauTreasury/script.js`, cukup pasang URL endpoint:

```javascript
/* ================= ENDPOINT MANDIRI ================= */
// Menggunakan Vercel Cloud (24/7 Online Permanen Gratis):
const MY_USD_IDR_API_URL = 'https://susdidr.vercel.app/api/index';
const MY_USD_IDR_WS_URL = ''; // Mode Cloud Vercel menggunakan polling otomatis 10s

// Atau jika dijalankan lokal di laptop:
// const MY_USD_IDR_WS_URL = 'ws://localhost:8000/ws';
// const MY_USD_IDR_API_URL = 'http://localhost:8000/api/pantau-treasury';

const USD_IDR_POLL_MS = 10 * 1000; 
const DEBUG = false;
```

---

## 🧪 Menjalankan Test Suite

```bash
python -m pytest tests/ -v
```
*(Seluruh 18 automated unit & integration tests terverifikasi 100% lulus).*
