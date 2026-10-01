const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const apiIndexPath = path.join(rootDir, 'api', 'index.js');

// 1. Dapatkan tanggal hari ini dalam format WIB (Asia/Jakarta, UTC+7)
const now = new Date();
const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Jakarta',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
});
const [fullYear, month, day] = formatter.format(now).split('-');
const todayDateStr = `${fullYear.slice(2)}.${month}.${day}`; // contoh: '26.10.01'
const todayPrefix = `v${todayDateStr}`;
const todayIsoDate = `${fullYear}-${month}-${day}`; // '2026-10-01'

// 2. Baca versi saat ini dari api/index.js
let apiContent = fs.readFileSync(apiIndexPath, 'utf8');
const versionMatch = apiContent.match(/const BACKEND_VERSION = ['"]v(\d{2}\.\d{2}\.\d{2})\.(\d+)['"];/);

let nextRevision = 1;
if (versionMatch) {
    const existingDate = versionMatch[1];
    const existingRev = parseInt(versionMatch[2], 10);
    if (existingDate === todayDateStr) {
        nextRevision = existingRev + 1;
    } else {
        nextRevision = 1;
    }
}

const newVersion = `${todayPrefix}.${nextRevision}`;

// 3. Update api/index.js
apiContent = apiContent.replace(
    /const BACKEND_VERSION = ['"][^'"]*['"];/,
    `const BACKEND_VERSION = '${newVersion}';`
);
apiContent = apiContent.replace(
    /const DEPLOYED_AT = ['"][^'"]*['"];/,
    `const DEPLOYED_AT = '${todayIsoDate}';`
);

fs.writeFileSync(apiIndexPath, apiContent, 'utf8');

console.log(`[ScrapingUSDIDR] Auto-bumped version: ${newVersion} (Date: ${todayIsoDate})`);
