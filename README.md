# USD/IDR Near Real-Time Scraper & REST API 🚀

Aplikasi Python modular untuk mengambil (*scraping*) kurs mata uang **USD ke IDR** dari Google Finance secara near real-time, menyimpan data secara cerdas dengan **deduplikasi** (hanya menyimpan saat nilai berubah), dan menyediakannya sebagai **FastAPI REST API & WebSocket** berkinerja tinggi yang siap dikonsumsi oleh website atau aplikasi dashboard Anda seperti **PantauTreasury**.

---

## 🌟 Fitur Utama

1. **Scraping Cepat & Andal**:
   - **Primary**: `requests` + `BeautifulSoup4` untuk parsing HTML statis yang sangat cepat dan hemat resource.
   - **Automatic Fallback**: Menggunakan `Playwright` headless browser secara otomatis jika Google Finance memerlukan JavaScript rendering atau bot detection.
2. **Deduplikasi Otomatis**:
   - Membandingkan nilai kurs baru dengan data terakhir di database.
   - Hanya menyimpan record baru jika kurs **berubah**, mencegah database membengkak dengan data duplikat.
3. **Integrasi Khusus PantauTreasury**:
   - Endpoint `/api/pantau-treasury` dengan struktur data yang langsung cocok dengan `state.usdIdrHistory` dan dropdown riwayat harga.
   - Endpoint WebSocket `/ws` untuk live push realtime tanpa perlu refresh/polling.
   - Drop-in mock endpoint `/v6/latest/USD` kompatibel dengan format `open.er-api.com`.
4. **Mode Hosting Gratis (Single-Service)**:
   - Dilengkapi fitur `RUN_POLLER_IN_APP=true` sehingga background scraper berjalan di background thread FastAPI secara otomatis. Anda cukup mendeploy **1 Web Service Gratis** di Koyeb/Render tanpa perlu membayar background worker tambahan!

---

## 💻 Cara Menjalankan Secara Lokal

### Mengatasi Masalah `uvicorn: command not found` di Windows
Jika perintah `uvicorn` tidak dikenali di PowerShell, gunakan prefix `python -m`:

```bash
# Menjalankan FastAPI Server (otomatis menjalankan Scraper di background jika RUN_POLLER_IN_APP=true)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Atau jika ingin menjalankan scraper dan API di 2 terminal terpisah:
- **Terminal 1 (Scraper Poller)**: `python -m scraper.poller`
- **Terminal 2 (API Server)**: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`

---

## 🔗 Panduan Integrasi ke Project PantauTreasury

Di dalam file `D:\A DEV\PantauTreasury\script.js`:

### Opsi 1: Integrasi Paling Mudah (Ganti 1 Baris URL)
Ubah konstanta `USD_IDR_API_URL` pada baris ke-22 di `script.js`:

```javascript
// Ganti:
// const USD_IDR_API_URL = 'https://open.er-api.com/v6/latest/USD';

// Menjadi (jika lokal):
const USD_IDR_API_URL = 'http://localhost:8000/v6/latest/USD';

// Atau (jika sudah di-deploy ke Cloud/Koyeb/Render):
// const USD_IDR_API_URL = 'https://<app-name-anda>.koyeb.app/v6/latest/USD';
```

### Opsi 2: Integrasi Kaya Fitur (`/api/pantau-treasury`)
Ganti fungsi fallback di `connectUsdIdrFeed` dalam `script.js` agar mengambil riwayat lengkap:

```javascript
async function fetchUsdIdrFromScraper() {
    try {
        const res = await fetch('http://localhost:8000/api/pantau-treasury');
        const data = await res.json();
        if (!data.success) throw new Error(data.message);

        // Update riwayat kurs di dashboard
        state.usdIdrHistory = data.history;
        renderUsdIdrHistoryDropdown();

        // Render kurs terkini
        const previous = state.usdIdrLastPrice;
        renderUsdIdrRate(data.price_formatted, `Live ${data.time}`, previous);
        scheduleUsdIdrPoll();
    } catch (e) {
        console.error('Gagal fetch scraper:', e);
        setUsdIdrUnavailableStatus('Tidak tersedia');
    }
}
```

---

## ☁️ Cara Hosting GRATIS 100% (24/7 Online)

Platform gratis terbaik untuk menjalankan scraper Python + FastAPI:

### 🏆 Opsi 1: Koyeb (Paling Direkomendasikan - 100% Gratis & 24/7 Tanpa Sleep)
Koyeb menyediakan **1 Free Nano Service** yang menyala 24/7 tanpa batas waktu dan tidak tertidur (no cold start).

1. Upload folder `ScrapingUSDIDR` ini ke GitHub (buat repository baru di GitHub).
2. Buka [https://www.koyeb.com](https://www.koyeb.com) dan buat akun gratis.
3. Klik **Create App** -> Pilih **GitHub**.
4. Pilih repositori `ScrapingUSDIDR` Anda.
5. Pada builder setting:
   - **Build type**: `Dockerfile` (Koyeb akan membaca Dockerfile otomatis) atau `Buildpack`
   - **Environment Variables**:
     - `RUN_POLLER_IN_APP=true`
     - `ENVIRONMENT=production`
     - `CORS_ALLOWED_ORIGINS=*`
6. Klik **Deploy**.
7. Anda akan mendapatkan URL publik HTTPS gratis, contoh: `https://usdidr-api-username.koyeb.app`.
8. Pasang URL tersebut di project `PantauTreasury` Anda!

---

### 🥈 Opsi 2: Render.com (Gratis)
1. Buka [https://render.com](https://render.com) -> Buat akun.
2. Klik **New +** -> **Web Service** -> Hubungkan GitHub repo Anda.
3. Pilih **Runtime: Python 3** (atau Docker).
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
6. Tambahkan Environment Variable:
   - `RUN_POLLER_IN_APP=true`
7. Klik **Deploy Web Service**.

---

### 🥉 Opsi 3: Hugging Face Spaces (Gratis Docker 24/7)
1. Buka [https://huggingface.co/spaces](https://huggingface.co/spaces) -> **Create new Space**.
2. Pilih **Space SDK**: **Docker** (Blank).
3. Push kode project ini ke repo Hugging Face Space.
4. Otomatis berjalan 24/7 di port 7860/8000 dengan 2 vCPU gratis!

---

## 🧪 Testing Suite

Jalankan test suite unit & integrasi (18 test kasus):
```bash
pytest tests/ -v
```
