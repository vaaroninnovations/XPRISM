// Screenshots the drawn card art for Exp 35-43 (illustrations.html), for make.py to size.
// Needs Playwright and an installed Chrome. Usage: node draw.js <outdir> [35,36,...]
const { chromium } = require('playwright');
const path = require('path');
const { pathToFileURL } = require('url');
const OUT = process.argv[2];
const ONLY = (process.argv[3] || '35,36,37,38,39,40,41,42,43').split(',');
const PAGE = pathToFileURL(path.join(__dirname, 'illustrations.html')).href;

(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await b.newPage({ viewport: { width: 800, height: 500 }, deviceScaleFactor: 2 });
  let bad = 0;
  p.on('pageerror', e => { bad++; console.log('page error:', e.message); });
  p.on('requestfailed', r => { bad++; console.log('failed:', r.url()); });
  for (const n of ONLY) {
    await p.goto(`${PAGE}?n=${n}`);
    await p.evaluate(() => Promise.all(['800 20px Inter', '700 20px "JetBrains Mono"', '700 20px DSEG7'].map(f => document.fonts.load(f))));
    await p.waitForTimeout(900);
    await p.screenshot({ path: path.join(OUT, n + '.png') });
  }
  console.log('done, problems:', bad);
  await b.close();
})();
