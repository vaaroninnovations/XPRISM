// All 43 experiments through the app: practice mode capture + exam-mode lockdown (staff preview).
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:8095';
const FNS = ['runAllInstant', 'runAll', 'guidedRun', 'doseAllInstant', 'runCompleteBatchExperiment', 'fillAllMockData', 'fillSampleVideoDataset', 'loadReferenceDataset'];
(async () => {
  const b = await chromium.launch();
  async function session(user, pw) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 950 } }); await ctx.addInitScript(() => { try { localStorage.setItem('xprism-cookies', 'essential'); } catch (e) { } });
    await ctx.route('**/*', r => r.request().url().startsWith(BASE) ? r.continue() : r.abort());
    const p = await ctx.newPage(); p.on('dialog', d => d.accept());
    await p.goto(BASE + '/accounts/login/'); await p.fill('#id_username', user); await p.fill('#id_password', pw);
    await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Login")')]);
    if (p.url().includes('/consent/')) { await p.check('#id_accept'); await p.check('#id_age_ok'); await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Accept and continue")')]); }
    await p.goto(BASE + '/');
    if (await p.$('#ethicsModal')) { await p.check('#ethicsModal input[name=agree_ethics]'); await Promise.all([p.waitForLoadState('load'), p.click('#ethicsModal button:has-text("I agree")')]); }
    return p;
  }
  const st = await session('demo-bp001', 'Demo@Student2026');
  const fac = await session('demo-faculty', 'Demo@Faculty2026');
  await st.goto(BASE + '/modules/');
  const slugs = await st.evaluate(async () => [...new Set([...document.querySelectorAll('a.expCard')].map(a => a.getAttribute('href').split('?')[0]))]);
  let fails = 0;
  for (const s of slugs) {
    const errs = []; const h1 = e => errs.push(e.message); st.on('pageerror', h1);
    await st.goto(BASE + s); await st.waitForTimeout(700);
    const mode = await st.evaluate(() => window.MCP_BRIDGE && MCP_BRIDGE.ctx.mode);
    const fn = await st.evaluate(names => { const f = names.find(n => typeof window[n] === 'function'); try { if (f) window[f](); } catch (e) { return 'ERR ' + e.message; } return f || 'none'; }, FNS);
    await st.waitForTimeout(500);
    const cap = await st.evaluate(() => {
      try { switchTab('observation'); } catch (e) { }
      try { if (typeof QUIZ !== 'undefined') QUIZ.forEach((q, i) => { const r = document.querySelector(`input[name="q${i}"][value="${q.a}"]`); if (r) r.checked = true; }); } catch (e) { }
      const d = MCP_BRIDGE.collect();
      return { completion: d.completion, results: d.results ? d.results.rows.length : 0, tables: d.tables.length, viva: d.viva ? `${d.viva.score}/${d.viva.total}` : '—', answer: d.answer ? `truth=${String(d.answer.truth).slice(0, 12)}` : '—' };
    });
    st.off('pageerror', h1);
    // exam-mode preview as faculty
    const errs2 = []; const h2 = e => errs2.push(e.message); fac.on('pageerror', h2);
    await fac.goto(BASE + s + '?exam=1'); await fac.waitForTimeout(900);
    const visibleShortcuts = await fac.evaluate(() => [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null && /reference dataset|run the (full|complete)|complete (all|both|full|the latin|control)|guided run|instant-run|instant-record|skip waiting|record full|assistant (processes|measures)|auto-complete|dose all|pilot:|record standard series/i.test(b.innerText)).map(b => b.innerText.trim().slice(0, 30)));
    fac.off('pageerror', h2);
    const good = mode === 'practice' && !errs.length && !errs2.length && cap.completion && !visibleShortcuts.length;
    if (!good) fails++;
    console.log(`${good ? 'ok  ' : 'FAIL'} ${s.split('/').pop().slice(0, 44).padEnd(44)} run=${fn.padEnd(26)} done=${cap.completion} res=${cap.results} tbl=${cap.tables} viva=${cap.viva.padEnd(4)} ${cap.answer.padEnd(18)} examLeft=${visibleShortcuts.length}${visibleShortcuts.length ? ' ' + visibleShortcuts.join('|') : ''} ${errs.concat(errs2).join(' | ').slice(0, 120)}`);
  }
  console.log(`\n${slugs.length - fails}/${slugs.length} experiments OK`);
  await b.close();
})();
