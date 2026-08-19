// ==============================================================================
// Vercel Serverless Function (Node.js Native - 100% Fast & Reliable)
// ==============================================================================

let memoryHistory = [];

export default async function handler(req, res) {
    // Header CORS agar bisa dipanggil dari domain mana pun
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', '*');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    try {
        let price = null;
        let changePercent = -0.17;

        // 1. Coba Scraping Google Finance
        try {
            const gfRes = await fetch('https://www.google.com/finance/quote/USD-IDR?hl=en', {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9,id;q=0.8'
                }
            });

            if (gfRes.ok) {
                const html = await gfRes.text();
                
                // Regex Harga Quote Utama Google Finance
                const priceMatch = html.match(/class="N6SYTe"[^>]*>[\s\S]*?jsname="Pdsbrc"[^>]*>(?:<span>)?([0-9,]+\.[0-9]+)(?:<\/span>)?/) 
                                || html.match(/class="YMlKec fxKbKc"[^>]*>([0-9,]+\.[0-9]+)</);
                
                if (priceMatch && priceMatch[1]) {
                    price = parseFloat(priceMatch[1].replace(/,/g, ''));
                }

                // Regex Persentase Perubahan
                const changeMatch = html.match(/class="DAicsd"[^>]*>[\s\S]*?([+-]?[0-9]+\.[0-9]+%)/)
                                 || html.match(/class="JwB6zf"[^>]*>([+-]?[0-9]+\.[0-9]+%)</);
                
                if (changeMatch && changeMatch[1]) {
                    changePercent = parseFloat(changeMatch[1].replace(/%/g, '').replace(/,/g, ''));
                }
            }
        } catch (e) {
            // Abaikan error Google Finance dan lanjut ke fallback
        }

        // 2. Fallback jika Google Finance gagal: Gunakan Open Exchange Rate API
        if (!price) {
            try {
                const erRes = await fetch('https://open.er-api.com/v6/latest/USD');
                if (erRes.ok) {
                    const erData = await erRes.json();
                    if (erData && erData.rates && erData.rates.IDR) {
                        price = parseFloat(erData.rates.IDR);
                    }
                }
            } catch (e) {
                // Abaikan error fallback
            }
        }

        // 3. Fallback jika semua offline
        if (!price) {
            price = memoryHistory.length ? memoryHistory[memoryHistory.length - 1].value : 17800.0;
        }

        const now = new Date();
        const timeLabel = now.toTimeString().split(' ')[0];

        const item = {
            price: price.toFixed(4),
            time: timeLabel,
            value: price,
            change_percent: changePercent
        };

        // Simpan ke riwayat jika berbeda dari harga terakhir
        if (!memoryHistory.length || memoryHistory[memoryHistory.length - 1].price !== item.price) {
            memoryHistory.push(item);
            if (memoryHistory.length > 50) memoryHistory.shift();
        }

        const responsePayload = {
            success: true,
            pair: 'USD/IDR',
            price: price,
            price_formatted: price.toFixed(4),
            change_percent: changePercent,
            time: timeLabel,
            timestamp: now.toISOString(),
            history: memoryHistory,
            usd_idr_history: memoryHistory
        };

        return res.status(200).json(responsePayload);

    } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
    }
}
