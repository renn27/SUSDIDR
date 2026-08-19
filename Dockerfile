# Multi-stage / Production-ready Dockerfile for Scraper & FastAPI
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install system dependencies needed for Playwright headless browser
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    curl \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser & dependencies
RUN playwright install chromium

# Copy project source files
COPY . .

# Create persistent storage and log directories
RUN mkdir -p /app/data /app/logs

# Expose API port
EXPOSE 8000

# Default command (overridden in docker-compose for scraper/api)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
