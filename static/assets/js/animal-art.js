/* XPRISM shared animal art: albino Wistar rat, Swiss albino mouse, albino rabbit,
 * guinea pig and Indian bullfrog.
 *
 * Fur and skin are baked ahead of time into static/assets/img/animals/ by
 * tools/animal-sprites (individually painted hairs over a lit height field).
 * Tails, whiskers, frog legs and side-view eyes stay vector so they can pose
 * and animate.
 *
 * The coordinates are shared with the experiments and must not move: side views
 * face +x, top views have the head at +x, origin = body centre, side-view eye at
 * (34,-4.8) (cage overlays draw a closed lid there).
 */
(function (global) {
  'use strict';

  // Bump after re-baking: nginx caches /assets/ for 30 days.
  const ANI_VER = 5;
  const BASE = new URL('../img/animals/', document.currentScript.src).href;
  const BOX = {
    'side-rat': [-38, -23, 50, 20], 'side-mouse': [-38, -23, 50, 20], earS: [16.5, -22, 30, -7.5],
    footH: [-23, 8, 3, 19], footHfar: [-23, 8, 3, 19], footF: [18, 9, 32, 19], footFfar: [18, 9, 32, 19],
    top: [-27, -16, 32, 16], 'top-mouse': [-24.27, -11.86, 28.83, 11.78], 'top-rat': [-25.06, -14.23, 28.77, 14.16], rbHead: [-152, -130, 152, 150], rbEar: [20, -244, 112, -70], rbBody: [-264, 84, 264, 256],
    guineaPig: [112, 28, 906, 412], frogBody: [428, 84, 572, 286], frogVen07: [96, 28, 564, 448], frogVen12: [330, 48, 670, 566]
  };

  const f2 = v => (Math.round(v * 100) / 100).toString();
  const lerp = (a, b, t) => a + (b - a) * t;

  // Each drawing is a plain <image>, which always repaints when its file arrives.
  // Holding a preloaded Image keeps the file in the browser's memory cache, so scenes
  // that rebuild their markup every frame reuse it instead of loading it again.
  const held = new Map();
  function sprite(name, attrs = '') {
    const b = BOX[name], url = `${BASE}${name}.webp?v=${ANI_VER}`;
    if (!held.has(name)) { const im = new Image(); im.src = url; held.set(name, im); }
    return `<image x="${b[0]}" y="${b[1]}" width="${b[2] - b[0]}" height="${b[3] - b[1]}" preserveAspectRatio="none" decoding="sync" ${attrs} href="${url}"/>`;
  }

  // tapered, ringed tail built from an SVG cubic chain
  function tailArt(d, w0, w1) {
    const n = (d.match(/-?\d*\.?\d+/g) || []).map(Number), P = [[n[0], n[1]]];
    for (let i = 2; i + 5 < n.length; i += 6) {
      const a = P[P.length - 1], b = [n[i], n[i + 1]], c = [n[i + 2], n[i + 3]], e = [n[i + 4], n[i + 5]];
      for (let s = 1; s <= 22; s++) { const t = s / 22, u = 1 - t; P.push([0, 1].map(j => u * u * u * a[j] + 3 * u * u * t * b[j] + 3 * u * t * t * c[j] + t * t * t * e[j])); }
    }
    const m = P.length - 1, N = P.map((p, i) => { const a = P[Math.max(0, i - 1)], b = P[Math.min(m, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1; return [-dy / l, dx / l]; });
    const W = i => lerp(w0, w1, i / m) / 2, rib = (off, sc) => {
      const pt = (i, s) => `${f2(P[i][0] + N[i][0] * (off * W(i) + s * W(i) * sc))} ${f2(P[i][1] + N[i][1] * (off * W(i) + s * W(i) * sc))}`;
      return 'M' + P.map((_, i) => pt(i, 1)).join('L') + 'L' + P.map((_, i) => pt(m - i, -1)).join('L') + 'Z';
    };
    let rings = '';
    for (let i = 1; i < m; i++) rings += `M${f2(P[i][0] + N[i][0] * W(i))} ${f2(P[i][1] + N[i][1] * W(i))}L${f2(P[i][0] - N[i][0] * W(i))} ${f2(P[i][1] - N[i][1] * W(i))}`;
    return `<path d="${rib(0, 1)}" fill="#dcaab0"/><path d="${rib(.5, .5)}" fill="#ad747f" opacity=".3"/><path d="${rib(-.38, .4)}" fill="#f6dcdb" opacity=".5"/><path d="${rings}" fill="none" stroke="#9f6a76" stroke-width=".08" opacity=".38"/>`;
  }
  function tube(pts, w0, w1, belly = 0) {
    const n = pts.length - 1, L = [], R = [];
    pts.forEach((p, i) => { const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1, t = i / n, w = (lerp(w0, w1, t) + belly * Math.sin(Math.PI * t)) / 2; L.push([p[0] - dy / l * w, p[1] + dx / l * w]); R.push([p[0] + dy / l * w, p[1] - dx / l * w]); });
    return 'M' + L.concat(R.reverse()).map(p => `${f2(p[0])} ${f2(p[1])}`).join('L') + 'Z';
  }
  const WHISK_D = (x, y, dir, sc) => [[-13, 23, -11], [-10, 27, -15.5], [-6, 30, -17], [-2.5, 31, -13], [1, 29, -7.5], [3.5, 26, -2], [6, 23, 3.5], [8.5, 20, 8]]
    .map(([a, L, e], i) => `M${f2(x - dir * (i % 3) * .55)} ${f2(y + (i - 3.5) * .42 * sc)}Q${f2(x + dir * L * .52 * sc)} ${f2(y + a * .42 * sc)} ${f2(x + dir * L * sc)} ${f2(y + e * sc * .85)}`).join('');
  const whiskerPaint = (d, w) => `<path d="${d}" fill="none" stroke="#5c4f49" stroke-opacity=".26" stroke-width="${f2(w * 1.75)}" stroke-linecap="round"/><path d="${d}" fill="none" stroke="#fffaf2" stroke-opacity=".86" stroke-width="${w}" stroke-linecap="round"/>`;

  const ANI_DEFS = `
      <filter id="furStrand" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".55 .08" numOctaves="3" seed="12" result="n"/><feColorMatrix in="n" values="0 0 0 0 .52  0 0 0 0 .46  0 0 0 0 .43  0 0 0 .75 -.2"/><feComposite in2="SourceGraphic" operator="in"/></filter>
      <filter id="furStrandT" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".12 .6" numOctaves="3" seed="21" result="n"/><feColorMatrix in="n" values="0 0 0 0 .52  0 0 0 0 .46  0 0 0 0 .43  0 0 0 .75 -.2"/><feComposite in2="SourceGraphic" operator="in"/></filter>
      <filter id="furFuzz" x="-6%" y="-8%" width="112%" height="116%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="3" result="t"/><feDisplacementMap in="SourceGraphic" in2="t" scale="2.4" xChannelSelector="R" yChannelSelector="G"/></filter>
      <filter id="aniBlur"><feGaussianBlur stdDeviation="1.6"/></filter>
      <filter id="aniSoft"><feGaussianBlur stdDeviation=".5"/></filter>
      <linearGradient id="aniBody" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".4" stop-color="#f7f3f0"/><stop offset=".78" stop-color="#e6ddd9"/><stop offset="1" stop-color="#c9bcb7"/></linearGradient>
      <linearGradient id="aniBodyT" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#fbf8f6"/><stop offset=".5" stop-color="#f1ebe7"/><stop offset="1" stop-color="#ddd2cd"/></linearGradient>
      <linearGradient id="aniShade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".6" stop-color="#9a8782" stop-opacity="0"/><stop offset="1" stop-color="#5f4c48" stop-opacity=".38"/></linearGradient>
      <linearGradient id="aniTail" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#efbdc6"/><stop offset="1" stop-color="#dc98a8"/></linearGradient>
      <radialGradient id="aniEye" cx=".36" cy=".3" r=".78"><stop offset="0" stop-color="#c62e49"/><stop offset=".42" stop-color="#7a0e22"/><stop offset=".82" stop-color="#34040d"/><stop offset="1" stop-color="#180206"/></radialGradient>
      <radialGradient id="aniEar" cx=".5" cy=".62" r=".65"><stop offset="0" stop-color="#fcd7df"/><stop offset=".7" stop-color="#f2adbf"/><stop offset="1" stop-color="#e48fa6"/></radialGradient>
      <linearGradient id="aniPaw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6bcc8"/><stop offset="1" stop-color="#e395a8"/></linearGradient>
      <radialGradient id="rbNoseG" cx=".42" cy=".3" r=".8"><stop offset="0" stop-color="#eab9c3"/><stop offset=".7" stop-color="#cf95a2"/><stop offset="1" stop-color="#ad6f7f"/></radialGradient>
      <clipPath id="aniClipB"><rect x="-70" y="-40" width="97" height="80"/></clipPath><clipPath id="aniClipH"><rect x="24" y="-40" width="40" height="80"/></clipPath>`;

  const memo = {};
  const once = (key, fn) => memo[key] || (memo[key] = fn());
  const TAILS = { rat: 'M-30 3 C-44 4 -52 12 -64 10 C-72 9 -76 14 -82 12', mouse: 'M-30 3 C-48 5 -58 -2 -70 5 C-80 10 -90 8 -96 14', top: 'M-20 0 C-30 3 -38 -3 -50 2 C-56 5 -60 2 -64 5' };

  // ---- side view. o: {sw (paw swelling 0..1), ink, kind:'rat'|'mouse', noTail, noFeet (caller poses the legs),
  //      headGroup (wrap the head in <g class="head"> so it can turn)}  Returns art only (no marks).
  function animalSideArt(o = {}) {
    const kind = o.kind === 'mouse' ? 'mouse' : 'rat', mouse = kind === 'mouse', sc = mouse ? .47 : 1, sw = o.sw || 0;
    const earRot = mouse ? -12 : -20, earS = mouse ? 1.42 : .94, eR = mouse ? 1.06 : .84;
    const tail = o.noTail ? '' : once('tail' + kind, () => tailArt(TAILS[kind], mouse ? 4.2 : 3.6, mouse ? 1.2 : .95));
    const wh = once('wh', () => whiskerPaint(WHISK_D(41.6, 2.6, 1, 1), .24));
    const ax = -14, ay = 15;
    return `<g transform="scale(${sc})"><g class="lvBreath">
        <ellipse cx="2" cy="17" rx="${mouse ? 40 : 36}" ry="3.2" fill="#000" opacity=".3" filter="url(#aniBlur)"/>
        ${tail}
        ${o.noFeet ? '' : `<g transform="translate(3.4 -1.1)">${sprite('footHfar')}</g><g transform="translate(-3.2 -1)">${sprite('footFfar')}</g>
        ${sprite('footF')}`}
        ${o.noFeet ? '' : `<g class="lvPaw" data-sw="${sw}"><g transform="translate(${ax} ${ay}) scale(${f2(1 + sw * .5)} ${f2(1 + sw * .85)}) translate(${-ax} ${-ay})">${sprite('footH')}</g>${sw ? `<ellipse cx="-13" cy="15" rx="${f2(8 + sw * 3.6)}" ry="${f2(2.3 + sw * 1.9)}" fill="#d43f52" opacity="${f2(sw * .42)}" filter="url(#aniSoft)"/>` : ''}</g>`}
        ${o.headGroup ? `<g clip-path="url(#aniClipB)">${sprite('side-' + kind)}</g><g class="head"><g clip-path="url(#aniClipH)">${sprite('side-' + kind)}</g>` : sprite('side-' + kind)}
        <g class="lvEar"><g transform="rotate(${earRot} 23 -12) translate(${f2(23 * (1 - earS))} ${f2(-13 * (1 - earS))}) scale(${earS})">${sprite('earS')}</g></g>
        <g transform="translate(34 -4.8) scale(${eR})"><ellipse rx="2.5" ry="2.26" fill="#120206"/><ellipse rx="2.14" ry="1.94" fill="url(#aniEye)"/><ellipse cx="-.72" cy="-.76" rx=".5" ry=".36" fill="#fff" opacity=".92"/><circle cx=".84" cy=".66" r=".18" fill="#fff" opacity=".35"/><path d="M-2.5 -1.1 Q0 -2.9 2.5 -1.2" fill="none" stroke="#cf9d9c" stroke-width=".26" opacity=".85"/></g>
        <ellipse class="lvLid" cx="34" cy="-4.8" rx="3" ry="2.75" fill="#ece2dc" opacity="0"/>
        <g class="lvWhisk">${wh}</g>${o.headGroup ? '</g>' : ''}
        ${o.ink ? `<line x1="-19" y1="14.3" x2="-11" y2="14.3" stroke="#1e3a8a" stroke-width="1.1"/>` : ''}
        </g></g>`;
  }

  // ---- top view (head to +x). o: {kind, noTail (caller draws its own)}. The rat is the mouse render reshaped: tools/animal-sprites.
  function animalTopArt(o = {}) {
    const mouse = o.kind === 'mouse', render = mouse || o.kind === 'rat';
    const tail = o.noTail ? '' : once(mouse ? 'tailTm' : 'tailT', () => tailArt(TAILS.top, mouse ? 2.2 : 2.7, .8));
    const wh = once('whT', () => whiskerPaint([-1, 1].map(s => [[3, 12, 4.4], [5.5, 15, 8], [8, 13.5, 11.5], [10, 11, 13.5]].map(([a, L, e], i) => `M${f2(25.2 - i * .7)} ${f2(s * (1.2 + i * .35))}Q${f2(25 + L * .55)} ${f2(s * (1.6 + a * .55))} ${f2(25 + L)} ${f2(s * (2 + e))}`).join('')).join(''), .17));
    return `<g transform="scale(.72)">
        ${render ? '<ellipse cx="2.4" cy="2" rx="25.5" ry="10.4" fill="#000" opacity=".26" filter="url(#aniBlur)"/>' : '<ellipse cx="0" cy="2.6" rx="24" ry="11" fill="#000" opacity=".26" filter="url(#aniBlur)"/>'}
        ${tail}${sprite(render ? 'top-' + o.kind : 'top')}${wh}
        </g>`;
  }

  // ---- albino rabbit, front view centred on the origin. o: {earTop (y of ear tips), body}
  function realRabbitHead(o = {}) {
    const T = o.earTop || -230, ky = f2((T + 90) / (-230 + 90));
    const ear = s => `<g transform="scale(${s} 1) translate(0 -90) scale(1 ${ky}) translate(0 90)">${sprite('rbEar')}</g>`;
    const wh = [[-1, -5, 30], [-1, 2, 36], [-1, 9, 34], [-1, -9, 25], [-1, 13, 28], [1, -5, 30], [1, 2, 36], [1, 9, 34], [1, -9, 25], [1, 13, 28]].map(([s, dy, l]) => `<path d="M${s * 22} ${84 + dy * .4} Q${s * (22 + l * 1.8)} ${76 + dy} ${s * (22 + l * 3)} ${92 + dy * 2.2}" fill="none" stroke="#fffaf2" stroke-opacity=".82" stroke-width=".55"/>`).join('');
    const nose = `<path d="M-10 65.5 Q0 59 10 65.5 Q6 75.5 0 77.5 Q-6 75.5 -10 65.5Z" fill="url(#rbNoseG)"/><path d="M-6.4 68.8 Q-3 72 -1.1 70 M6.4 68.8 Q3 72 1.1 70" fill="none" stroke="#6f3648" stroke-width="1" stroke-linecap="round"/>`;
    const HEAD = 'M0 -112 C50 -116 106 -96 128 -48 C144 -10 124 42 88 84 C62 112 32 132 0 134 C-32 132 -62 112 -88 84 C-124 42 -144 -10 -128 -48 C-106 -96 -50 -116 0 -112Z', BODY = 'M-250 250 C-230 130 -130 96 0 96 C130 96 230 130 250 250Z';
    // a soft cast shadow keeps white fur readable on the pale scene backgrounds
    const cast = d => `<path d="${d}" fill="#4a3a34" opacity=".34" filter="url(#realBlur)" transform="translate(2 7)"/>`;
    return `${o.body ? cast(BODY) + sprite('rbBody') : ''}${cast(HEAD)}<g class="rbEarL">${ear(-1)}</g><g class="rbEarR">${ear(1)}</g>${sprite('rbHead')}<g class="rbNose">${nose}</g><g class="rbWhisk">${wh}</g>`;
  }
  // one eye, in page coordinates. pupilId is kept so the experiment can resize the pupil.
  function realRabbitEye(cx, cy, r, pupilId, pupilR) {
    return `<ellipse cx="${cx}" cy="${cy}" rx="${r * 1.55}" ry="${r * 1.35}" fill="url(#rbSocket)" opacity=".7"/>
        <ellipse cx="${cx}" cy="${cy}" rx="${r * 1.1}" ry="${r * 1.02}" fill="#6a2c3a"/>
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#rbIris)"/>
        <circle ${pupilId ? `id="${pupilId}" ` : ''}cx="${cx}" cy="${cy}" r="${pupilR}" fill="#2a0510" opacity=".92"/>
        <ellipse cx="${cx - r * .34}" cy="${cy - r * .36}" rx="${r * .2}" ry="${r * .13}" fill="#fff" opacity=".9"/>
        <path d="M${cx - r * 1.3} ${cy - r * .05} Q${cx} ${cy - r * 2.05} ${cx + r * 1.3} ${cy - r * .05} Q${cx} ${cy - r * 1.72} ${cx - r * 1.3} ${cy - r * .05}Z" fill="#ece4df"/>
        <path d="M${cx - r * 1.3} ${cy - r * .05} Q${cx} ${cy - r * 1.72} ${cx + r * 1.3} ${cy - r * .05}" fill="none" stroke="#6d4b4d" stroke-width="${r * .07}" opacity=".6"/>`;
  }
  // A cut-out render with its studio shadow baked in pale. Multiplying makes that read as a shadow, but an SVG
  // blends only with its own content, so the caller must paint the bench behind this inside the same SVG.
  function realGuineaPig() { return sprite('guineaPig', 'style="mix-blend-mode:multiply"'); }
  function realFrogBody() { return sprite('frogBody'); }
  // belly-up frog on the dissection board: '07' or '12', drawn in that experiment's scene coordinates
  function frogVentralArt(layout) { return sprite('frogVen' + layout); }
  // hind leg, posable: hip -> knee -> foot. Heavy marbled thigh, pale long webbed toes.
  function realFrogLeg(hipX, kneeX, kneeY, footX, footY, side) {
    const curve = (a, c, b, n = 14) => Array.from({ length: n + 1 }, (_, i) => { const t = i / n, u = 1 - t; return [u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]; });
    const thigh = curve([hipX, 252], [kneeX + side * 8, (kneeY + 252) / 2], [kneeX, kneeY]);
    const shank = curve([kneeX, kneeY], [(kneeX + footX) / 2 + side * 3, (kneeY + footY) / 2], [footX, footY]);
    let seed = 7919; const rn = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const blotches = (p, w0, w1, b, n, col, op) => { let o = ''; for (let i = 0; i < n; i++) { const k = 1 + Math.floor(rn() * (p.length - 2)), t = k / (p.length - 1), a = p[k - 1], c = p[k + 1], dx = c[0] - a[0], dy = c[1] - a[1], l = Math.hypot(dx, dy) || 1, w = (lerp(w0, w1, t) + b * Math.sin(Math.PI * t)) * .4 * (rn() * 2 - 1), rx = 1 + rn() * w0 * .15, ry = .7 + rn() * w0 * .07, cx = f2(p[k][0] - dy / l * w), cy = f2(p[k][1] + dx / l * w); o += `<ellipse cx="${cx}" cy="${cy}" rx="${f2(rx)}" ry="${f2(ry)}" transform="rotate(${Math.round(Math.atan2(dy, dx) * 57.3)} ${cx} ${cy})" fill="${col}" opacity="${op}"/>`; } return o; };
    const seg = (p, w0, w1, b, n) => `<path d="${tube(p, w0 + 1.2, w1 + 1.2, b)}" fill="#2e3312"/><path d="${tube(p, w0, w1, b)}" fill="#6f7a30"/><path d="${tube(p.map(q => [q[0] + side * w0 * .28, q[1]]), w0 * .3, w1 * .3, b * .2)}" fill="#3f4418" opacity=".22"/>${blotches(p, w0, w1, b, n, '#26220f', .9)}${blotches(p, w0, w1, b, Math.round(n * .7), '#b8b868', .55)}<path d="${tube(p.map(q => [q[0] - side * w0 * .18, q[1] - w0 * .08]), w0 * .24, w1 * .24, b * .2)}" fill="#f4f6d0" opacity=".14"/>`;
    const toes = [-.72, -.36, 0, .36, .72].map((a, i) => [footX + Math.sin(a) * (24 + (i === 3 ? 15 : i * 2.5)), footY + Math.cos(a) * (24 + (i === 3 ? 15 : i * 2.5))]);
    const toe = (p, w0, w1, col) => `<path d="${tube([[footX, footY], [(footX + p[0]) / 2, (footY + p[1]) / 2], p], w0, w1)}" fill="${col}"/>`;
    return `<path d="M${footX} ${footY} L${toes.map(p => f2(lerp(footX, p[0], .78)) + ' ' + f2(lerp(footY, p[1], .78))).join(' L')}Z" fill="#c2a78c" opacity=".78"/>
        ${toes.map(p => toe(p, 4.2, 2.2, '#6e5a48') + toe(p, 3, 1.5, '#d0b39b')).join('')}
        ${seg(shank, 13, 7.5, 3, 16)}${seg(thigh, 22, 12, 8, 26)}`;
  }

  // Rendered dissection plates and anatomy references: static/assets/img/frog/.
  // Bump after replacing a file: nginx caches /assets/ for 30 days.
  const FROG_VER = 1;
  const FROG_BASE = new URL('../img/frog/', document.currentScript.src).href;
  function frogPlateUrl(name) {
    const url = `${FROG_BASE}${name}.webp?v=${FROG_VER}`;
    if (!held.has(url)) { const im = new Image(); im.src = url; held.set(url, im); }
    return url;
  }
  // one render of w x h pixels, mapped into the scene by t = {s, x, y}
  function frogPlate(name, w, h, t, attrs = '') {
    return `<image href="${frogPlateUrl(name)}" x="${t.x}" y="${t.y}" width="${f2(w * t.s)}" height="${f2(h * t.s)}" preserveAspectRatio="none" decoding="sync" ${attrs}/>`;
  }

  // Anatomy reference shared by the frog experiments.
  const ANATOMY = [
    { tab: 'External', img: 'frog-dorsal-3d', alt: 'Dorsal view of an intact frog', note: 'Dorsal view: moist skin, a pale mid-dorsal stripe, protruding eyes, a tympanum behind each eye and webbed hind feet.' },
    { tab: 'Body cavity', img: 'frog-internal-anatomy-viscera-3d', alt: 'Frog body cavity opened from the ventral side', note: 'Ventral wall opened: heart, lungs, liver with gall bladder, stomach, coiled intestine, kidney and fat bodies.' },
    { tab: 'Heart', img: 'frog-heart-in-situ-3d', alt: 'Frog heart in place with the pericardium reflected', note: 'Heart in place with the pericardium reflected: one ventricle, two atria and the branching truncus arteriosus.' }
  ];
  let anatomy = null;
  function buildAnatomy() {
    const root = document.createElement('div');
    root.id = 'frogAnatomy';
    root.style.cssText = 'display:none;position:fixed;inset:0;z-index:60;background:rgba(15,23,42,.8);align-items:center;justify-content:center;padding:16px';
    root.innerHTML = `<div role="dialog" aria-modal="true" aria-labelledby="faTitle" style="background:#fff;border-radius:16px;width:100%;max-width:56rem;max-height:100%;overflow:auto;padding:20px;box-shadow:0 25px 50px -12px rgba(0,0,0,.5)">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px">
          <h3 id="faTitle" style="font-size:16px;font-weight:700;color:#1e293b;margin:0">Frog anatomy reference (3D renders)</h3>
          <button type="button" data-fa="close" aria-label="Close" style="min-width:32px;min-height:32px;border:0;background:none;font-size:18px;color:#64748b;cursor:pointer">✕</button>
        </div>
        <div role="tablist" aria-label="Views" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">${ANATOMY.map((a, i) => `<button type="button" role="tab" data-fa="${i}" style="font-size:12px;font-weight:600;padding:6px 12px;border-radius:7px;border:1px solid #cbd5e1;cursor:pointer">${a.tab}</button>`).join('')}</div>
        <div role="tabpanel"><img data-fa="img" alt="" style="display:block;width:100%;max-height:62vh;object-fit:contain;background:#0b1220;border-radius:10px"><p data-fa="note" style="font-size:12px;line-height:1.5;color:#64748b;margin:10px 0 0;text-align:center"></p></div>
      </div>`;
    document.body.appendChild(root);
    const tabs = [...root.querySelectorAll('[role=tab]')], img = root.querySelector('[data-fa=img]'), note = root.querySelector('[data-fa=note]'), closeBtn = root.querySelector('[data-fa=close]');
    const box = {
      root,
      show(i) {
        const a = ANATOMY[i];
        img.src = frogPlateUrl(a.img); img.alt = a.alt; note.textContent = a.note;
        tabs.forEach((t, n) => { const on = n === i; t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1; t.style.background = on ? '#0a1f44' : '#fff'; t.style.color = on ? '#fff' : '#0a1f44'; });
      },
      close() { root.style.display = 'none'; if (box.opener && box.opener.focus) box.opener.focus(); },
      open() { box.opener = document.activeElement; root.style.display = 'flex'; box.show(0); closeBtn.focus(); }
    };
    root.addEventListener('click', e => {
      if (e.target === root || e.target.closest('[data-fa=close]')) { box.close(); return; }
      const t = e.target.closest('[role=tab]'); if (t) box.show(+t.dataset.fa);
    });
    root.addEventListener('keydown', e => {
      if (e.key === 'Escape') { box.close(); return; }
      const tab = e.target.closest('[role=tab]');
      if (tab && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) { const i = (+tab.dataset.fa + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length; box.show(i); tabs[i].focus(); }
      if (e.key === 'Tab') {   // keep focus inside the dialog
        const cur = tabs.find(t => t.tabIndex === 0);
        if (e.shiftKey && document.activeElement === closeBtn) { e.preventDefault(); cur.focus(); }
        else if (!e.shiftKey && document.activeElement === cur) { e.preventDefault(); closeBtn.focus(); }
      }
    });
    return box;
  }
  function openFrogAnatomy() { (anatomy = anatomy || buildAnatomy()).open(); }

  Object.assign(global, { ANI_DEFS, animalSideArt, animalTopArt, realRabbitHead, realRabbitEye, realGuineaPig, realFrogBody, realFrogLeg, frogVentralArt, frogPlate, frogPlateUrl, openFrogAnatomy });
})(window);
