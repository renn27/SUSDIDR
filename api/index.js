// ==============================================================================
// USD/IDR & Treasury Gold Unified Edge Serverless Function
// High Performance, Multi-Tier Fallback, Smart Minute Caching, WIB (UTC+7)
// ==============================================================================

// In-Memory Cache untuk USD/IDR
let usdMemoryCache = {
    data: null,
    lastFetchedAt: 0,
    ttlMs: 3000 // Cache 3 detik
};
let usdMemoryHistory = [];

// In-Memory Cache untuk Emas Treasury
let goldMemoryCache = {
    data: null,
    lastFetchedAt: 0,
    minuteBucket: null
};
let goldMemoryHistory = [];

/**
 * Format waktu saat ini ke Waktu Indonesia Barat (WIB / Asia/Jakarta, UTC+7)
 */
function getWibTimeInfo() {
    const now = new Date();
    
    // Format HH:MM:SS dalam zona waktu Asia/Jakarta (WIB)
    const timeFormatter = new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Asia/Jakarta',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
    const timeWib = timeFormatter.format(now);

    // Format YYYY-MM-DD HH:mm untuk minute bucket
    const minuteFormatter = new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Asia/Jakarta',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });
    const minuteBucketKey = minuteFormatter.format(now);

    // Detik saat ini dalam WIB
    const parts = timeWib.split(':');
    const currentSecond = parseInt(parts[2], 10) || 0;
    const currentMinute = parseInt(parts[1], 10) || 0;

    // Format ISO standar UTC untuk sinkronisasi waktu client-server yang akurat
    const isoWib = now.toISOString();

    return { timeWib, isoWib, rawDate: now, minuteBucketKey, currentSecond, currentMinute };
}

/**
 * Normalisasi format menit dari string updated_at Treasury (e.g. "2026-08-26 19:35:02")
 */
function getTreasuryMinuteBucket(dateStr) {
    if (!dateStr) return null;
    try {
        const d = new Date(dateStr.replace(' ', 'T') + '+07:00');
        if (Number.isNaN(d.getTime())) return null;
        const minuteFormatter = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Asia/Jakarta',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
        return minuteFormatter.format(d);
    } catch (e) {
        return null;
    }
}

/**
 * 1. Mengambil data kurs USD/IDR dari Google Finance dengan Fast-Path Regex & Fallback
 */
async function fetchExchangeRate({ force = false } = {}) {
    const nowMs = Date.now();
    
    // Kembalikan cache jika masih dalam batas TTL 3 detik (kecuali force refresh)
    if (!force && usdMemoryCache.data && (nowMs - usdMemoryCache.lastFetchedAt < usdMemoryCache.ttlMs)) {
        return usdMemoryCache.data;
    }

    let price = null;
    let changePercent = -0.17;
    let source = 'unknown';

    // TIER 1: Google Finance Scraping (Fast-Path Regex < 0.2ms)
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3500);

        const gfRes = await fetch('https://www.google.com/finance/quote/USD-IDR?hl=en', {
            signal: controller.signal,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Cache-Control': 'no-cache'
            }
        });
        clearTimeout(timeoutId);

        if (gfRes.ok) {
            const html = await gfRes.text();
            
            // Fast-Path Regex untuk Harga USD/IDR
            const priceMatch = html.match(/class="N6SYTe"[^>]*>[\s\S]*?jsname="Pdsbrc"[^>]*>(?:<span>)?([0-9,]+\.[0-9]+)(?:<\/span>)?/)
                            || html.match(/class="YMlKec fxKbKc"[^>]*>([0-9,]+\.[0-9]+)</);
            
            if (priceMatch && priceMatch[1]) {
                price = parseFloat(priceMatch[1].replace(/,/g, ''));
                source = 'google-finance';
            }

            // Fast-Path Regex untuk Persentase Perubahan
            const changeMatch = html.match(/class="DAicsd"[^>]*>[\s\S]*?([+-]?[0-9]+\.[0-9]+%)/)
                             || html.match(/class="JwB6zf"[^>]*>([+-]?[0-9]+\.[0-9]+%)</);
            
            if (changeMatch && changeMatch[1]) {
                changePercent = parseFloat(changeMatch[1].replace(/%/g, '').replace(/,/g, ''));
            }
        }
    } catch (e) {
        // Fallback gracefully
    }

    // TIER 2: Open Exchange Rates API Fallback
    if (!price) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);

            const erRes = await fetch('https://open.er-api.com/v6/latest/USD', { signal: controller.signal });
            clearTimeout(timeoutId);

            if (erRes.ok) {
                const erData = await erRes.json();
                if (erData && erData.rates && erData.rates.IDR) {
                    price = parseFloat(erData.rates.IDR);
                    source = 'open-er-fallback';
                }
            }
        } catch (e) {
            // Fallback gracefully
        }
    }

    // TIER 3: Memori Cache Terakhir
    if (!price) {
        if (usdMemoryHistory.length) {
            price = usdMemoryHistory[usdMemoryHistory.length - 1].value;
            changePercent = usdMemoryHistory[usdMemoryHistory.length - 1].change_percent;
            source = 'memory-fallback';
        } else {
            price = 17800.00;
            source = 'default-fallback';
        }
    }

    const { timeWib, isoWib } = getWibTimeInfo();

    const result = {
        pair: 'USD/IDR',
        price: price,
        price_formatted: price.toFixed(4),
        change_percent: changePercent,
        time: timeWib,
        timezone: 'WIB (UTC+7)',
        timestamp: isoWib,
        source: source
    };

    // Deduplikasi Riwayat USD/IDR: Hanya tambahkan jika harga berubah
    const historyItem = {
        price: result.price_formatted,
        time: timeWib,
        value: price,
        change_percent: changePercent
    };

    if (!usdMemoryHistory.length || usdMemoryHistory[usdMemoryHistory.length - 1].price !== historyItem.price) {
        usdMemoryHistory.push(historyItem);
        if (usdMemoryHistory.length > 10) {
            usdMemoryHistory.shift();
        }
    }

    // Perbarui in-memory cache
    usdMemoryCache = {
        data: result,
        lastFetchedAt: nowMs,
        ttlMs: 3000
    };

    return result;
}

/**
 * 2. Mengambil data Harga Emas dari API Resmi Treasury (api.treasury.id)
 * Dilengkapi Smart Minute Caching & Perhitungan Metrik Otomatis
 */
async function fetchTreasuryGold({ force = false } = {}) {
    const timeInfo = getWibTimeInfo();
    const nowMs = Date.now();

    // SMART MINUTE CACHE:
    // Jika data menit saat ini sudah valid di cache dan BUKAN force refresh,
    // kita gunakan cache. Tapi jika detik 00-08 atau belum menit aktif, selalu tembak live!
    const isMinuteTransition = timeInfo.currentSecond <= 8;
    const isCacheValid = !force && !isMinuteTransition && 
                         goldMemoryCache.data && 
                         goldMemoryCache.minuteBucket === timeInfo.minuteBucketKey;

    if (isCacheValid) {
        return goldMemoryCache.data;
    }

    let buy = null;
    let sell = null;
    let updatedAt = null;
    let source = 'treasury-live';

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);

        const res = await fetch('https://api.treasury.id/api/v1/antigrvty/gold/rate', {
            method: 'POST',
            signal: controller.signal,
            headers: {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-ID,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,id;q=0.6',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            }
        });
        clearTimeout(timeoutId);

        if (res.ok) {
            const json = await res.json();
            if (json && json.data) {
                buy = Number(json.data.buying_rate);
                sell = Number(json.data.selling_rate);
                updatedAt = json.data.updated_at;
            }
        }
    } catch (err) {
        // Fallback gracefully
    }

    // Fallback ke data memory jika request gagal
    if ((!buy || !sell) && goldMemoryCache.data) {
        return goldMemoryCache.data;
    }

    if (!buy || !sell) {
        buy = 1450000;
        sell = 1390000;
        updatedAt = timeInfo.timeWib;
        source = 'default-fallback';
    }

    // Kalkulasi Metrik Finansial Standar PantauTreasury
    const spread = buy - sell;
    const spreadPercent = parseFloat(((spread / buy) * 100).toFixed(2));
    const gramBeli60m = Math.floor((60000000 / buy) * 10000) / 10000;
    const gramJual58m = Math.floor((58005000 / sell) * 10000) / 10000;
    const nilaiJual = Math.round((60000000 / buy) * sell);
    const cuan = Math.round(nilaiJual - 58005000);

    const goldMinuteBucket = getTreasuryMinuteBucket(updatedAt);
    const isCurrentMinute = goldMinuteBucket === timeInfo.minuteBucketKey;

    const result = {
        buy: buy,
        sell: sell,
        spread: spread,
        spread_percent: spreadPercent,
        gram_beli_60m: gramBeli60m,
        gram_jual_58m: gramJual58m,
        nilai_jual: nilaiJual,
        cuan: cuan,
        updated_at: updatedAt || timeInfo.timeWib,
        is_current_minute: isCurrentMinute,
        source: source
    };

    // Deduplikasi Riwayat Emas: Hanya tambahkan jika harga beli/jual berubah
    const historyItem = {
        buy: buy,
        sell: sell,
        time: updatedAt ? updatedAt.split(' ')[1] || timeInfo.timeWib : timeInfo.timeWib,
        updated_at: updatedAt || timeInfo.timeWib
    };

    if (!goldMemoryHistory.length || 
        goldMemoryHistory[goldMemoryHistory.length - 1].buy !== historyItem.buy ||
        goldMemoryHistory[goldMemoryHistory.length - 1].sell !== historyItem.sell) {
        goldMemoryHistory.push(historyItem);
        if (goldMemoryHistory.length > 10) {
            goldMemoryHistory.shift();
        }
    }

    // Perbarui in-memory cache
    goldMemoryCache = {
        data: result,
        lastFetchedAt: nowMs,
        minuteBucket: isCurrentMinute ? timeInfo.minuteBucketKey : null
    };

    return result;
}

/**
 * Handler Utama Vercel Serverless Function
 */
export default async function handler(req, res) {
    // Headers CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cache-Control');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    try {
        const timeInfo = getWibTimeInfo();
        const isMinuteTransition = timeInfo.currentSecond <= 8;

        // Cek apakah request meminta force live refresh (misal tombol refresh besar atau detik 1 auto-sync)
        const isForce = req.query.force === 'true' || 
                        req.query.refresh === 'true' || 
                        isMinuteTransition ||
                        (req.headers['cache-control'] && req.headers['cache-control'].includes('no-cache'));

        // Caching Header:
        // Saat detik 00-08 (jendela rilis Treasury) atau saat force refresh -> NO-CACHE sama sekali agar CDN tidak menahan data lama!
        // Saat detik 09-59 dan data sudah aktif -> Cache 3 detik di CDN edge untuk efisiensi
        if (isForce || isMinuteTransition) {
            res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
            res.setHeader('Pragma', 'no-cache');
            res.setHeader('Expires', '0');
        } else {
            res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=3, stale-while-revalidate=3');
        }

        // Eksekusi paralel Google Finance USD/IDR dan Treasury Gold
        const [rateResult, goldResult] = await Promise.allSettled([
            fetchExchangeRate({ force: isForce }),
            fetchTreasuryGold({ force: isForce })
        ]);

        const rateData = rateResult.status === 'fulfilled' ? rateResult.value : (usdMemoryCache.data || {
            pair: 'USD/IDR', price: 17800.0, price_formatted: '17800.0000', change_percent: 0.0, time: '00:00:00'
        });

        const goldData = goldResult.status === 'fulfilled' ? goldResult.value : (goldMemoryCache.data || {
            buy: 1450000, sell: 1390000, spread: 60000, spread_percent: 4.14, updated_at: '-'
        });

        const usdHistory = usdMemoryHistory.length ? usdMemoryHistory : [{
            price: rateData.price_formatted,
            time: rateData.time,
            value: rateData.price,
            change_percent: rateData.change_percent
        }];

        const goldHistory = goldMemoryHistory.length ? goldMemoryHistory : [{
            buy: goldData.buy,
            sell: goldData.sell,
            time: goldData.updated_at ? goldData.updated_at.split(' ')[1] || rateData.time : rateData.time,
            updated_at: goldData.updated_at
        }];

        // ETag Caching (HTTP 304 Not Modified) hanya di luar jendela transisi menit
        if (!isForce && !isMinuteTransition) {
            const etag = `"${goldData.buy}-${goldData.sell}-${rateData.price_formatted}-${goldData.updated_at || ''}-${usdHistory.length}-${goldHistory.length}"`;
            res.setHeader('ETag', etag);

            const clientEtag = req.headers['if-none-match'];
            if (clientEtag && (clientEtag === etag || clientEtag.replace(/^W\//, '') === etag.replace(/^W\//, ''))) {
                return res.status(304).end();
            }
        }

        const responsePayload = {
            success: true,
            server_time: timeInfo.timeWib,
            timezone: 'WIB (UTC+7)',
            timestamp: timeInfo.isoWib,
            gold: goldData,
            usd_idr: rateData,
            gold_history: goldHistory,
            usd_idr_history: usdHistory
        };

        return res.status(200).json(responsePayload);

    } catch (err) {
        return res.status(500).json({
            success: false,
            error: err.message || 'Internal Server Error'
        });
    }
}
