@echo off
title USD/IDR Scraper & Cloudflare Tunnel
echo ============================================================
echo   Menyalakan USD/IDR Scraper + API Server + Cloudflare Tunnel
echo ============================================================

start "FastAPI Server" cmd /k "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "Cloudflare Tunnel" cmd /k "cloudflared.exe tunnel --url http://localhost:8000"

echo Server dan Tunnel berhasil dijalankan!
