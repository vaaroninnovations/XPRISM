/* XPRISM shared lab bench.
   The tiled wall, epoxy bench, glassware, metals, silicone tubing and smoked-drum kymograph
   for the organ-bath stations, drawn to match the rig in Exp 13 and Exp 18.
   Each module keeps its own geometry and simulation: this file supplies only the materials
   (under the gradient ids the modules already use) and the fittings. */

// The room alone: for modules that keep their own instruments
const LAB_ROOM_DEFS = `
  <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#334155"/><stop offset=".35" stop-color="#1e293b"/><stop offset=".85" stop-color="#0f172a"/><stop offset="1" stop-color="#020617"/></linearGradient>
  <radialGradient id="spot" cx=".5" cy=".32" r=".68"><stop offset="0" stop-color="#60a5fa" stop-opacity=".18"/><stop offset=".45" stop-color="#38bdf8" stop-opacity=".06"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>
  <pattern id="labTile" width="60" height="34" patternUnits="userSpaceOnUse"><rect width="59" height="33" fill="#1e293b" fill-opacity=".35" stroke="#475569" stroke-width=".8" stroke-opacity=".3"/><line x1="0" y1="0" x2="59" y2="0" stroke="#94a3b8" stroke-width=".6" stroke-opacity=".25"/></pattern>
  <linearGradient id="bench" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1e2530"/><stop offset=".25" stop-color="#141a22"/><stop offset=".7" stop-color="#0d1117"/><stop offset="1" stop-color="#06090d"/></linearGradient>
  <linearGradient id="labBevel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#94a3b8"/><stop offset=".4" stop-color="#cbd5e1"/><stop offset="1" stop-color="#334155"/></linearGradient>`;

// The room plus the glass, metals and fluids of the organ-bath rig
const LAB_DEFS = `${LAB_ROOM_DEFS}
  <filter id="labSoft" x="-30%" y="-200%" width="160%" height="500%"><feGaussianBlur stdDeviation="3"/></filter>
  <linearGradient id="glass" x1="0" x2="1"><stop offset="0" stop-color="#e0f2fe" stop-opacity=".65"/><stop offset=".1" stop-color="#fff" stop-opacity=".5"/><stop offset=".3" stop-color="#f0f9ff" stop-opacity=".12"/><stop offset=".65" stop-color="#e0f2fe" stop-opacity=".18"/><stop offset=".9" stop-color="#fff" stop-opacity=".45"/><stop offset="1" stop-color="#bae6fd" stop-opacity=".6"/></linearGradient>
  <linearGradient id="glassEdge" x1="0" x2="1"><stop offset="0" stop-color="#7dd3fc" stop-opacity=".85"/><stop offset=".3" stop-color="#fff" stop-opacity=".95"/><stop offset=".7" stop-color="#38bdf8" stop-opacity=".75"/><stop offset="1" stop-color="#0284c7" stop-opacity=".85"/></linearGradient>
  <linearGradient id="liquid" x1="0" x2="1"><stop offset="0" stop-color="#38bdf8" stop-opacity=".55"/><stop offset=".25" stop-color="#bae6fd" stop-opacity=".42"/><stop offset=".7" stop-color="#7dd3fc" stop-opacity=".48"/><stop offset="1" stop-color="#0284c7" stop-opacity=".6"/></linearGradient>
  <linearGradient id="jacketW" x1="0" x2="1"><stop offset="0" stop-color="#0284c7" stop-opacity=".3"/><stop offset=".3" stop-color="#7dd3fc" stop-opacity=".12"/><stop offset=".7" stop-color="#bae6fd" stop-opacity=".18"/><stop offset="1" stop-color="#0369a1" stop-opacity=".35"/></linearGradient>
  <linearGradient id="steel" x1="0" x2="1"><stop offset="0" stop-color="#334155"/><stop offset=".18" stop-color="#94a3b8"/><stop offset=".42" stop-color="#fff"/><stop offset=".68" stop-color="#cbd5e1"/><stop offset="1" stop-color="#1e293b"/></linearGradient>
  <linearGradient id="steelH" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#475569"/><stop offset=".25" stop-color="#f8fafc"/><stop offset=".65" stop-color="#94a3b8"/><stop offset="1" stop-color="#1e293b"/></linearGradient>
  <linearGradient id="castIron" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#475569"/><stop offset=".2" stop-color="#334155"/><stop offset=".65" stop-color="#1e293b"/><stop offset="1" stop-color="#0f172a"/></linearGradient>
  <linearGradient id="brass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fef08a"/><stop offset=".25" stop-color="#eab308"/><stop offset=".6" stop-color="#ca8a04"/><stop offset=".85" stop-color="#a16207"/><stop offset="1" stop-color="#713f12"/></linearGradient>
  <linearGradient id="brassH" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fef08a"/><stop offset=".3" stop-color="#eab308"/><stop offset=".7" stop-color="#ca8a04"/><stop offset="1" stop-color="#713f12"/></linearGradient>
  <linearGradient id="smokedDrum" x1="0" x2="1"><stop offset="0" stop-color="#06090e"/><stop offset=".1" stop-color="#111620"/><stop offset=".35" stop-color="#1c2432"/><stop offset=".55" stop-color="#243042"/><stop offset=".75" stop-color="#17202c"/><stop offset=".92" stop-color="#0c1017"/><stop offset="1" stop-color="#05070b"/></linearGradient>
  <linearGradient id="circBody" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#334155"/><stop offset=".3" stop-color="#1e293b"/><stop offset=".85" stop-color="#0f172a"/><stop offset="1" stop-color="#090d14"/></linearGradient>
  <linearGradient id="tissueGrad" x1="0" x2="1"><stop offset="0" stop-color="#fb7185"/><stop offset=".22" stop-color="#fda4af"/><stop offset=".48" stop-color="#ffe4e6"/><stop offset=".75" stop-color="#f43f5e"/><stop offset="1" stop-color="#be123c"/></linearGradient>`;

const LAB_STILL = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

function labRoom(benchY = 470) {
  return `<rect width="1000" height="${benchY}" fill="url(#wall)"/><rect width="1000" height="${benchY}" fill="url(#labTile)"/><rect width="1000" height="${benchY}" fill="url(#spot)"/>
    <rect y="${benchY - 3}" width="1000" height="6" fill="url(#labBevel)"/>
    <rect y="${benchY + 3}" width="1000" height="${557 - benchY}" fill="url(#bench)"/>
    <rect y="${benchY + 3}" width="1000" height="${557 - benchY}" filter="url(#grain)" opacity=".7"/>
    <rect y="${benchY + 4}" width="1000" height="2" fill="#fff" opacity=".07"/>`;
}

// Soft contact shadows where equipment meets the bench: [[centre x, y, half width], ...]
const labShadows = list => list.map(([x, y, r]) => `<ellipse cx="${x}" cy="${y + 2}" rx="${r}" ry="${Math.max(3.5, r * 0.1)}" fill="#000" opacity=".5" filter="url(#labSoft)"/>`).join('');

// Translucent silicone tubing: dark edge, tinted wall, one line of highlight
function labTube(d, w = 6, o = {}) {
  const round = 'fill="none" stroke-linecap="round" stroke-linejoin="round"';
  return `<path d="${d}" ${round} stroke="#0f172a" stroke-opacity=".5" stroke-width="${w + 1.6}"/><path d="${d}" ${round} stroke="${o.fill || '#cbd5e1'}" stroke-opacity=".62" stroke-width="${w}"/><path d="${d}" ${round} stroke="#fff" stroke-opacity=".7" stroke-width="${Math.max(0.8, w * 0.22)}" transform="translate(${-w * 0.16} ${-w * 0.16})"/>`;
}

// What is moving inside a tube; shown and advanced by labFlowTick
const labFlowPath = (id, d, w = 2.4, c = '#7dd3fc') => `<path id="${id}" d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-dasharray="2 10" stroke-linecap="round" opacity="0"/>`;

function labFlowTick(id, on, dt, speed = 48) {
  const e = document.getElementById(id);
  if (!e) return;
  e.setAttribute('opacity', on ? 0.85 : 0);
  if (!on || LAB_STILL) return;
  const off = (parseFloat(e.dataset.off || 0) - dt * speed) % 120;
  e.dataset.off = off;
  e.setAttribute('stroke-dashoffset', off.toFixed(1));
}

function labStandBase(x, y, w, h = 10) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="2" fill="url(#castIron)" stroke="#475569" stroke-width=".7"/><rect x="${x + 3}" y="${y + 1}" width="${w - 6}" height="1.2" fill="#fff" opacity=".18"/>`;
}

function labBoss(x, y, w = 22, h = 18) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" fill="url(#castIron)" stroke="#475569" stroke-width=".7"/><circle cx="${x + w / 2}" cy="${y + h / 2}" r="4" fill="url(#brass)" stroke="#78350f" stroke-width=".7"/><rect x="${x + w / 2 - 1.2}" y="${y - 5}" width="2.4" height="5" fill="url(#brassH)"/><rect x="${x + w / 2 - 4}" y="${y - 7}" width="8" height="2.6" rx="1" fill="url(#brass)"/>`;
}

// A length of intestine: bulges along its length, cross folds and a wet highlight
function labIleum(cx, tt, tb, w) {
  const h = tb - tt, n = 8, pts = [];
  const half = i => { const t = i / n; return w * (0.62 + 0.4 * Math.sin(t * Math.PI)) + (i % 2 ? w * 0.1 : -w * 0.04); };
  for (let i = 0; i <= n; i++) pts.push([cx - half(i), tb - h * i / n]);
  for (let i = n; i >= 0; i--) pts.push([cx + half(i), tb - h * i / n]);
  const mid = (a, b) => `${((a[0] + b[0]) / 2).toFixed(1)} ${((a[1] + b[1]) / 2).toFixed(1)}`;
  let d = `M${mid(pts[pts.length - 1], pts[0])}`;
  pts.forEach((p, i) => { d += `Q${p[0].toFixed(1)} ${p[1].toFixed(1)} ${mid(p, pts[(i + 1) % pts.length])}`; });
  const folds = [0.18, 0.36, 0.54, 0.72, 0.86].map(f => {
    const y = tb - h * f, c = half(Math.round(f * n)) * 0.88;
    return `<path d="M${(cx - c).toFixed(1)} ${y.toFixed(1)}Q${cx} ${(y + 2.5).toFixed(1)} ${(cx + c).toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="#be123c" stroke-width="1.2" stroke-opacity=".35"/>`;
  }).join('');
  return `<path d="${d}Z" fill="url(#tissueGrad)" stroke="#9f1239" stroke-width="1" stroke-opacity=".5"/><path d="M${cx - 2} ${(tb - 6).toFixed(1)}Q${(cx - 2 - w * 0.3).toFixed(1)} ${((tb + tt) / 2).toFixed(1)} ${cx - 2} ${(tt + 6).toFixed(1)}" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" opacity=".45"/>${folds}`;
}

// The Sherrington-type kymograph. Everything the modules update each frame keeps its id.
function labKymograph() {
  const DRUM = 'M712 60 L712 468 A103 9 0 0 0 918 468 L918 60 Z';
  const stripes = Array.from({ length: 12 }, (_, i) => `<rect x="${712 + i * 20}" y="60" width="1.5" height="410" fill="#fff" opacity=".06"/><rect x="${713.5 + i * 20}" y="60" width="1.5" height="410" fill="#0f172a" opacity=".1"/>`).join('');
  const screws = [[774, 490], [858, 490], [774, 508], [858, 508]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="1.2" fill="#713f12"/>`).join('');
  return `<g>
    ${labShadows([[815, 529, 138]])}
    <rect x="702" y="525" width="30" height="6" rx="2" fill="#090d14"/><rect x="898" y="525" width="30" height="6" rx="2" fill="#090d14"/>
    <rect x="690" y="466" width="250" height="62" rx="6" fill="url(#castIron)" stroke="#475569" stroke-width="1.2" filter="url(#sh)"/>
    <rect x="694" y="469" width="242" height="3" fill="#fff" opacity=".15"/>
    <rect x="768" y="486" width="96" height="26" rx="3" fill="url(#brass)" stroke="#78350f" stroke-width=".8"/>${screws}
    <text x="816" y="497" font-size="5.6" fill="#3b2003" text-anchor="middle" font-weight="800" font-family="Inter, sans-serif">C.F. PALMER-type</text>
    <text x="816" y="506" font-size="5" fill="#3b2003" text-anchor="middle" font-weight="700" font-family="Inter, sans-serif" letter-spacing=".3">SHERRINGTON KYMOGRAPH</text>
    <g class="hot" data-act="speed"><rect x="700" y="484" width="60" height="34" rx="4" fill="#090d14" stroke="#334155" stroke-width=".8"/><rect x="714" y="488" width="32" height="3" rx="1.5" fill="#000"/>
      <line id="gearLever" x1="730" y1="510" x2="718" y2="492" stroke="#f8fafc" stroke-width="3" stroke-linecap="round"/><circle cx="730" cy="510" r="4" fill="url(#brass)" stroke="#78350f" stroke-width=".6"/>
      <text id="gearTxt" x="730" y="526" font-size="7" fill="#fde68a" text-anchor="middle" font-family="JetBrains Mono"></text></g>
    <g class="hot" data-act="switch"><rect x="872" y="484" width="58" height="34" rx="4" fill="#090d14" stroke="#334155" stroke-width=".8"/><rect id="swKnob" x="880" y="492" width="18" height="18" rx="3" fill="#b91c1c"/>
      <text id="swTxt" x="914" y="505" font-size="8" fill="#fca5a5" text-anchor="middle" font-weight="800"></text></g>
    <ellipse cx="815" cy="470" rx="110" ry="11" fill="url(#brassH)" stroke="#78350f" stroke-width=".8"/>
    <rect x="810" y="18" width="10" height="42" fill="url(#steel)"/>
    <g class="hot" data-act="paper">
      <path d="${DRUM}" fill="url(#steel)"/>
      <path id="paperBg" d="${DRUM}" fill="#111" opacity="0"/>
      <path id="paperSmoke" d="${DRUM}" filter="url(#smokeF)" opacity="0"/>
      <g clip-path="url(#drumClip)"><g id="drumStripes">${stripes}</g><polyline id="drumTrace" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><g id="drumMarks"></g></g>
      <path d="${DRUM}" fill="url(#drumShade)"/>
      <path d="${DRUM}" fill="none" stroke="#000" stroke-opacity=".5" stroke-width="1.5"/>
    </g>
    <ellipse cx="815" cy="60" rx="106" ry="10" fill="url(#brassH)" stroke="#78350f" stroke-width=".8"/>
    <ellipse cx="815" cy="60" rx="94" ry="7.4" fill="#0f172a" opacity=".55"/>
    <ellipse cx="815" cy="60" rx="18" ry="3.6" fill="url(#steelH)" stroke="#334155" stroke-width=".6"/>
    <rect x="794" y="38" width="42" height="12" rx="3" fill="url(#brassH)" stroke="#78350f" stroke-width=".8"/>
    <g transform="translate(838 18)"><rect width="84" height="20" rx="4" fill="#090d14" stroke="#334155"/><circle id="drumLed" cx="10" cy="10" r="3.5" fill="#eab308"/><circle id="drumHalo" cx="10" cy="10" r="6.5" fill="#eab308" opacity=".22"/><text id="drumLabel" x="20" y="13.5" font-size="7.5" font-weight="700" fill="#fbbf24" font-family="JetBrains Mono">STOPPED</text></g>
  </g>`;
}

// Per-frame state of the drum: status lamp and the surface moving past the pen
function labDrumTick(running, neutral, travel) {
  const led = document.getElementById('drumLed');
  if (!led) return;
  const colour = running ? '#4ade80' : '#fbbf24';
  led.setAttribute('fill', running ? '#22c55e' : '#eab308');
  document.getElementById('drumHalo').setAttribute('fill', running ? '#22c55e' : '#eab308');
  const label = document.getElementById('drumLabel');
  label.textContent = running ? 'RUNNING ▸' : neutral ? 'NEUTRAL' : 'STOPPED';
  label.setAttribute('fill', colour);
  if (!LAB_STILL) document.getElementById('drumStripes').setAttribute('transform', `translate(${(-(travel % 20)).toFixed(1)} 0)`);
}
