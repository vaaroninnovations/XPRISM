// Screenshots each module's main scene from the running site, for make.py to crop.
// Needs the site at http://127.0.0.1:8095 with the demo accounts and Playwright, as in tests/README.md.
// Usage: node shoot.js <outdir> [03,04,...]
const { chromium } = require('playwright');
const path = require('path');
const BASE = process.env.XPRISM_BASE || 'http://127.0.0.1:8095';
const OUT = process.argv[2];
const ONLY = (process.argv[3] || '').split(',').filter(Boolean);

(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 2 });
  await ctx.addInitScript(() => { try { localStorage.setItem('xprism-cookies', 'essential'); } catch (e) { } });
  const p = await ctx.newPage(); p.on('dialog', d => d.accept());
  await p.goto(BASE + '/accounts/login/'); await p.fill('#id_username', 'demo-faculty'); await p.fill('#id_password', 'Demo@Faculty2026');
  await Promise.all([p.waitForURL(u => !u.pathname.endsWith('/accounts/login/')), p.click('button:has-text("Login")')]);
  if (p.url().includes('/consent/')) { await p.check('#id_accept'); await p.check('#id_age_ok'); await Promise.all([p.waitForURL(u => !u.pathname.includes('/consent/')), p.click('button:has-text("Accept and continue")')]); }
  await p.goto(BASE + '/modules/');
  const slugs = await p.evaluate(() => [...new Set([...document.querySelectorAll('a.expCard')].map(a => a.getAttribute('href').split('?')[0]))]);
  let bad = 0;
  for (const s of slugs.sort()) {
    const n = s.split('/').pop().slice(0, 2);
    if (ONLY.length && !ONLY.includes(n)) continue;
    const errs = []; const h = e => errs.push(e.message); p.on('pageerror', h);
    await p.goto(BASE + s); await p.waitForTimeout(700);
    await p.addStyleTag({ content: '.pulse{animation:none!important;filter:none!important;outline:none!important}' });
    await p.addScriptTag({ path: path.join(__dirname, 'recipes.js') });
    const res = await p.evaluate(n => window.__shot(n), n);
    await p.waitForTimeout(n === '01' ? 3000 : 1500);
    await p.evaluate(() => Promise.all([...document.images].map(i => i.decode ? i.decode().catch(() => { }) : 0)));
    const target = ['13', '18', '22'].includes(n) ? '#benchArea' : '#scene';
    const el = await p.$(target) || await p.$('#benchArea') || await p.$('main');
    await el.screenshot({ path: path.join(OUT, n + '.png') });
    if (res !== 'ok' || errs.length) { bad++; console.log(n, res, errs.join(' | ').slice(0, 200)); }
    p.off('pageerror', h);
  }
  console.log('done, problems:', bad);
  await b.close();
})();
