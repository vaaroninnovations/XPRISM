// Renders the XPRISM ad images with the project's own fonts, logo and simulation screenshots.
// Change the demo login below, then run:  npm i --no-save playwright-core && node marketing/ads/build_ads.js
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require('playwright-core');

const SITE = 'xprism.drvara.si', ID = 'xprismdemo', PWD = 'Xprism@2026';
const ROOT = 'file:///' + path.resolve(__dirname, '../..').replace(/\\/g, '/');

const css = `
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;height:100%}
body{color:#fff;font-family:Inter,sans-serif;background-color:#08193b;overflow:hidden;
  background-image:radial-gradient(760px 620px at 92% 2%,rgba(126,19,181,.72),transparent 72%),radial-gradient(760px 560px at 10% 100%,rgba(6,110,170,.55),transparent 72%),linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);
  background-size:auto,auto,40px 40px,40px 40px}
.ad{position:relative;width:100%;height:100%;display:flex;flex-direction:column;padding:var(--pad)}
.top{display:flex;align-items:center;justify-content:space-between;gap:24px}
.logo{background:#fff;border-radius:calc(var(--u)*14);padding:calc(var(--u)*10) calc(var(--u)*18);display:flex}
.logo img{height:calc(var(--u)*62);width:auto;display:block}
.tag{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:calc(var(--u)*21);letter-spacing:.06em;color:#5ee0d3;text-transform:uppercase;text-align:right}
h1{font-family:Poppins,sans-serif;font-weight:800;letter-spacing:-.025em;line-height:1.07;font-size:var(--h);margin-top:calc(var(--u)*34)}
h1 span{color:#5ee0d3}
.sub{margin-top:calc(var(--u)*18);font-size:var(--s);line-height:1.38;color:#dbe2ef}
.shot{flex:1 1 0;min-height:0;margin-top:calc(var(--u)*28);border-radius:calc(var(--u)*20);overflow:hidden;border:calc(var(--u)*2) solid rgba(255,255,255,.28);box-shadow:0 calc(var(--u)*20) calc(var(--u)*50) rgba(0,0,0,.45);background:#f4f2f9}
.shot img{width:100%;height:100%;object-fit:cover;display:block}
.rs{display:flex;gap:calc(var(--u)*14);margin-top:calc(var(--u)*24)}
.rs div{flex:1;padding:calc(var(--u)*16) calc(var(--u)*18);border-top:calc(var(--u)*6) solid #7e13b5;background:rgba(255,255,255,.08);border-radius:0 0 calc(var(--u)*12) calc(var(--u)*12)}
.rs div:nth-child(2){border-color:#066eaa}.rs div:nth-child(3){border-color:#2bbfb0}
.rs b{display:block;font-family:Poppins,sans-serif;font-weight:700;font-size:calc(var(--u)*29)}
.rs span{display:block;margin-top:calc(var(--u)*4);font-size:calc(var(--u)*22);line-height:1.3;color:#dbe2ef}
.cred{margin-top:calc(var(--u)*24);background:#fff;color:#08193b;border-radius:calc(var(--u)*20);padding:calc(var(--u)*20) calc(var(--u)*28);box-shadow:0 calc(var(--u)*12) calc(var(--u)*34) rgba(0,0,0,.35)}
.cred h2{font-family:Poppins,sans-serif;font-weight:800;font-size:calc(var(--u)*30);color:#7e13b5;letter-spacing:-.01em}
.grid{display:flex;justify-content:space-between;gap:calc(var(--u)*20);margin-top:calc(var(--u)*10)}
.grid small{display:block;font-size:calc(var(--u)*20);font-weight:600;color:#475569}
.grid strong{display:block;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:calc(var(--u)*32);letter-spacing:-.02em;white-space:nowrap}
.rows .grid{flex-direction:column;gap:calc(var(--u)*6)}
.rows .grid div{display:flex;justify-content:space-between;align-items:baseline}
.pair{flex:1 1 0;min-height:0;display:flex;gap:calc(var(--u)*16);margin-top:calc(var(--u)*26)}
.pair .shot{flex:1.55 1 0;margin-top:0}
.pair .rs{flex:1 1 0;flex-direction:column;margin-top:0}
.pair .rs div{display:flex;flex-direction:column;justify-content:center}
/* landscape: copy beside the screenshot */
.wide{flex-direction:row;gap:calc(var(--u)*36);align-items:stretch}
.wide .col{flex:1 1 0;min-width:0;display:flex;flex-direction:column}
.wide .shot{margin-top:0}
.wide .cred{margin-top:auto}
.wide .grid{flex-direction:column;gap:calc(var(--u)*4)}
.wide .grid div{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.wide .side{flex:1.05 1 0;min-width:0;display:flex}
`;

const logo = `<div class="logo"><img src="${ROOT}/brand/xprism-lockup-transparent.png" alt=""></div>`;
const lab = '<div class="tag">Virtual<br>Pharmacology Lab</div>';
const motto = '<h1>Experiment Virtually.<br>Learn Practically.<br><span>Advance Ethically.</span></h1>';
const shot = (file, pos, extra = '') => `<div class="shot"><img src="${ROOT}/static/assets/img/modules/${file}" alt="" style="object-position:${pos};${extra}"></div>`;
const credOf = title => `<div class="cred"><h2>${title}</h2><div class="grid"><div><small>Website</small><strong>${SITE}</strong></div><div><small>Demo ID</small><strong>${ID}</strong></div><div><small>Password</small><strong>${PWD}</strong></div></div></div>`;
const cred = credOf("Try the demo now. It's free.");

const ads = [
  { name: 'xprism-ad-1-square-1080x1080', w: 1080, h: 1080, u: 1, pad: 52, hs: 76, ss: 31, body: `
    <div class="top">${logo}${lab}</div>${motto}
    ${shot('hero-rota-rod.jpg', '50% 72%')}${cred}` },
  { name: 'xprism-ad-2-story-1080x1920', w: 1080, h: 1920, u: 1.18, pad: 60, hs: 88, ss: 37, body: `
    <div style="height:70px"></div>
    <div class="top">${logo}${lab}</div>${motto}
    <p class="sub">25 interactive experimental pharmacology simulations, with observation sheets and viva questions.</p>
    ${shot('hero-rota-rod.jpg', '50% 72%')}
    <div class="rows">${cred}</div>
    <div style="height:150px"></div>` },
  { name: 'xprism-ad-3-landscape-1200x628', w: 1200, h: 628, u: .72, pad: 34, hs: 47, ss: 22, wide: true, body: `
    <div class="col">
      <div class="top">${logo}${lab}</div>
      <h1 style="margin-top:20px">Experiment Virtually.<br>Learn Practically.<br><span>Advance Ethically.</span></h1>
      <p class="sub">25 interactive pharmacology simulations.</p>
      ${cred}
    </div>
    <div class="side">${shot('hero-rota-rod.jpg', '9% 50%', 'transform:scale(1.2);transform-origin:9% 42%')}</div>` },
  { name: 'xprism-ad-4-3rs-square-1080x1080', w: 1080, h: 1080, u: 1, pad: 52, hs: 62, ss: 31, body: `
    <div class="top">${logo}${lab}</div>
    <h1>25 pharmacology practicals.<br><span>Not one live animal.</span></h1>
    <div class="pair">${shot('hero-plus-maze.jpg', '14% 50%')}
    <div class="rs"><div><b>Replacement</b><span>Simulations for teaching practicals</span></div><div><b>Reduction</b><span>Repeat and prepare digitally</span></div><div><b>Refinement</b><span>Learn humane, careful methods</span></div></div></div>
    ${cred}` },
  { name: 'xprism-ad-5-faculty-square-1080x1080', w: 1080, h: 1080, u: 1, pad: 52, hs: 76, ss: 31, body: `
    <div class="top">${logo}<div class="tag">For pharmacology<br>faculty &amp; colleges</div></div>
    <h1>Assign it. Time it.<br><span>Grade it.</span></h1>
    <p class="sub">Virtual practicals with batches, exam mode, viva questions, grading and marks export.</p>
    ${shot('hero-dose-response.jpg', '50% 40%')}${credOf("Try the student demo now. It's free.")}` },
];

(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const tmp = path.join(os.tmpdir(), 'xprism-ad.html');
  for (const a of ads) {
    fs.writeFileSync(tmp, `<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="${ROOT}/static/assets/css/theme.css"><style>${css}
      :root{--u:${a.u}px;--pad:${a.pad}px;--h:${a.hs}px;--s:${a.ss}px}</style><body><div class="ad${a.wide ? ' wide' : ''}">${a.body}</div></body>`);
    const p = await (await b.newContext({ viewport: { width: a.w, height: a.h } })).newPage();
    await p.goto('file:///' + tmp.replace(/\\/g, '/'), { waitUntil: 'networkidle' });
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(__dirname, a.name + '.png') });
    console.log(a.name);
    await p.close();
  }
  fs.unlinkSync(tmp);
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
