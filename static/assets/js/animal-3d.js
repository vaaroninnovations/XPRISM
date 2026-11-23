/* XPRISM 3D reference animal: a turntable view of the laboratory species a module uses, in its Task Description tab.
 *
 *   <script src="../assets/js/animal-3d.js" data-animals="mouse"></script>      (or "rat", or "mouse rat")
 *
 * The models (static/assets/models/albino-*.glb, real size in metres, with a sniffing and tail-sway animation) and the
 * viewer (Google <model-viewer> 3.5.0, Apache-2.0, vendored in js/vendor) are fetched only when the student opens the
 * panel, so the page itself loads no faster or slower than before.
 */
(function () {
  'use strict';
  const me = document.currentScript;
  const BASE = new URL('../', me.src).href;             // .../assets/
  const VER = 1;
  const ANIMALS = {
    mouse: {
      name: 'Swiss albino mouse', sci: 'Mus musculus', file: 'albino-mouse.glb',
      facts: [['Adult weight', '20–30 g'], ['Body length', '7.5–10 cm, tail about as long'], ['Heart rate', '500–600 /min'],
        ['Respiration', '100–200 /min'], ['Body temperature', '36.5–38 °C'], ['Blood volume', '≈ 72 mL/kg'], ['Life span', '1.5–2.5 years']],
      look: 'Note the pink eyes and skin of the albino, the large thin ears, and the long, scaly tail used for balance and heat loss.'
    },
    rat: {
      name: 'Wistar albino rat', sci: 'Rattus norvegicus', file: 'albino-rat.glb',
      facts: [['Adult weight', '150–300 g (as used)'], ['Body length', '20–25 cm, tail slightly shorter'], ['Heart rate', '300–500 /min'],
        ['Respiration', '70–115 /min'], ['Body temperature', '37–38 °C'], ['Blood volume', '≈ 64 mL/kg'], ['Life span', '2.5–3.5 years']],
      look: 'Compared with the mouse: a blunter head, smaller ears relative to the head, a thicker tail and a much larger body.'
    }
  };
  const kinds = (me.dataset.animals || 'mouse').split(/[\s,]+/).filter(k => ANIMALS[k]);
  if (!kinds.length) return;

  let viewerReady = null;
  const loadViewer = () => viewerReady || (viewerReady = customElements.get('model-viewer') ? Promise.resolve() : new Promise((ok, fail) => {
    const s = document.createElement('script');
    s.src = `${BASE}js/vendor/model-viewer-3.5.0.min.js?v=${VER}`; s.onload = ok; s.onerror = fail; document.head.appendChild(s);
  }));

  function build() {
    const host = document.querySelector('#viewTask .max-w-5xl') || document.getElementById('viewTask');
    if (!host || document.getElementById('a3d')) return;
    const card = document.createElement('section');
    card.id = 'a3d';
    card.className = 'rounded-xl border border-slate-200 bg-slate-50 p-4';
    const tabs = kinds.length > 1 ? `<div class="flex gap-1" role="tablist">${kinds.map((k, i) => `<button type="button" role="tab" data-k="${k}" aria-selected="${!i}" class="a3d-tab">${ANIMALS[k].name}</button>`).join('')}</div>` : '';
    card.innerHTML = `
      <style>
        #a3d .a3d-tab{border-color:#cbd5e1;color:#334155;background:#fff}#a3d .a3d-tab[aria-selected="true"]{background:#0f766e;border-color:#0f766e;color:#fff}
        #a3d model-viewer{width:100%;height:340px;background:radial-gradient(ellipse at 50% 70%,#ffffff 0%,#eef2f6 70%);border-radius:10px;--poster-color:transparent}
        #a3d .a3d-stage{position:relative;min-height:340px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;display:flex;align-items:center;justify-content:center}
        #a3d dl{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:12px}#a3d dt{color:#64748b}#a3d dd{color:#0f172a;font-weight:600;margin:0}
        #a3d .a3d-grid{display:grid;gap:16px;align-items:start}@media (min-width:768px){#a3d .a3d-grid{grid-template-columns:3fr 2fr}}
        #a3d .a3d-open{font:700 13px Inter,sans-serif;color:#fff;background:#0f766e;border-radius:8px;padding:8px 16px;box-shadow:0 1px 3px rgba(0,0,0,.2)}#a3d .a3d-open:hover{background:#115e59}
        #a3d .a3d-tab{font:700 11px Inter,sans-serif;padding:4px 10px;border-radius:5px;border-width:1px}
        @media (max-width:767px){#a3d model-viewer,#a3d .a3d-stage{height:280px;min-height:280px}}
      </style>
      <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h4 class="text-xs font-bold text-slate-700 uppercase tracking-wider">3D reference animal</h4>${tabs}
      </div>
      <div class="a3d-grid">
        <div class="a3d-stage" id="a3dStage">
          <button type="button" id="a3dOpen" class="a3d-open">View in 3D</button>
        </div>
        <div>
          <div class="text-sm font-bold text-slate-900" id="a3dName"></div>
          <div class="text-xs italic text-slate-500 mb-2" id="a3dSci"></div>
          <dl id="a3dFacts"></dl>
          <p class="text-xs text-slate-600 leading-relaxed mt-3" id="a3dLook"></p>
          <p class="text-[11px] text-slate-500 mt-2">Drag to turn it round, scroll or pinch to zoom. Typical values for healthy adults; your institution's figures may differ slightly.</p>
        </div>
      </div>`;
    host.appendChild(card);

    let cur = kinds[0], viewer = null;
    const show = k => {
      cur = k; const A = ANIMALS[k];
      card.querySelector('#a3dName').textContent = A.name;
      card.querySelector('#a3dSci').textContent = A.sci;
      card.querySelector('#a3dFacts').innerHTML = A.facts.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join('');
      card.querySelector('#a3dLook').textContent = A.look;
      card.querySelectorAll('.a3d-tab').forEach(b => b.setAttribute('aria-selected', String(b.dataset.k === k)));
      if (viewer) viewer.src = `${BASE}models/${A.file}?v=${VER}`;
    };
    card.querySelectorAll('.a3d-tab').forEach(b => b.addEventListener('click', () => show(b.dataset.k)));
    show(cur);

    card.querySelector('#a3dOpen').addEventListener('click', e => {
      const btn = e.currentTarget; btn.disabled = true; btn.textContent = 'Loading the 3D model…';
      loadViewer().then(() => {
        viewer = document.createElement('model-viewer');
        Object.entries({ src: `${BASE}models/${ANIMALS[cur].file}?v=${VER}`, alt: `3D model of a ${ANIMALS[cur].name}`, 'camera-controls': '', 'touch-action': 'pan-y',
          'auto-rotate': '', 'auto-rotate-delay': '1500', 'rotation-per-second': '18deg', autoplay: '', 'shadow-intensity': '1', 'shadow-softness': '.8', exposure: '1.05',
          'camera-orbit': '35deg 75deg auto', 'interaction-prompt': 'none' }).forEach(([k, v]) => viewer.setAttribute(k, v));
        const stage = card.querySelector('#a3dStage'); stage.innerHTML = ''; stage.appendChild(viewer);
      }).catch(() => { btn.disabled = false; btn.textContent = 'Could not load the 3D viewer: try again'; });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
