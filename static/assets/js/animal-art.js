/* XPRISM shared animal art: albino Wistar rat, Swiss albino mouse, albino rabbit,
 * guinea pig and Indian bullfrog.
 *
 * Fur and skin are baked ahead of time into static/assets/img/animals/ by
 * tools/animal-sprites (individually painted hairs over a lit height field).
 * Tails, whiskers, frog legs and side-view eyes stay vector so they can pose
 * and animate.
 *
 * The side-view rat is a photograph of an albino Wistar rat (rat-side-photo.webp) with a posable tail.
 *
 * The coordinates are shared with the experiments and must not move: side views
 * face +x, top views have the head at +x, origin = body centre, side-view eye at
 * (34,-4.8) (cage overlays draw a closed lid there).
 */
(function (global) {
  'use strict';

  // Bump after re-baking: nginx caches /assets/ for 30 days.
  const ANI_VER = 7;
  const BASE = new URL('../img/animals/', document.currentScript.src).href;
  const BOX = {
    'side-rat': [-38, -23, 50, 20], 'side-mouse': [-38, -23, 50, 20], earS: [16.5, -22, 30, -7.5],
    footH: [-23, 8, 3, 19], footHfar: [-23, 8, 3, 19], footF: [18, 9, 32, 19], footFfar: [18, 9, 32, 19],
    top: [-27, -16, 32, 16], 'top-mouse': [-24.27, -11.86, 28.83, 11.78], 'top-rat': [-25.06, -14.23, 28.77, 14.16], rbHead: [-114, -146, 116, 254], rbEarL: [-230, -366, -4, -30], rbEarR: [9, -356, 235, -30], rbBody: [-245, -146, 225, 526],
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
  // A tapering, ringed tail along a path of cubic curves, w0 wide at its start and w1 at its tip
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
      <clipPath id="aniClipB"><rect x="-70" y="-40" width="97" height="80"/></clipPath><clipPath id="aniClipH"><rect x="24" y="-40" width="40" height="80"/></clipPath>
      <filter id="aniRatFeather" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="7"/></filter>
      <filter id="aniMouseTone" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values=".62"/><feComponentTransfer><feFuncR type="linear" slope="1.02"/><feFuncG type="linear" slope="1.04" intercept=".01"/><feFuncB type="linear" slope="1.08" intercept=".02"/></feComponentTransfer></filter>
      <clipPath id="aniRatHM" clipPathUnits="userSpaceOnUse"><rect x="752" y="0" width="441" height="616"/></clipPath>
      <mask id="aniRatEarM" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><ellipse cx="814" cy="163" rx="38" ry="54" fill="url(#aniRatEyeG)" transform="rotate(14 814 163)"/></mask>
      <filter id="aniMouseTail" color-interpolation-filters="sRGB"><feColorMatrix type="hueRotate" values="-14"/><feColorMatrix type="saturate" values=".8"/></filter>
      <mask id="aniMsNT" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="667"><path fill="#fff" filter="url(#aniRatFeather)" d="M770 0H2000V667H770Z"/></mask>
      <mask id="aniMsNF" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="667"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H2000V380L1700 400L1560 470L1400 500L1200 492L1000 505L860 490L770 455L760 667H0Z"/></mask>
      <mask id="aniMsNFT" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="667"><path fill="#fff" filter="url(#aniRatFeather)" d="M770 0H2000V380L1700 400L1560 470L1400 500L1200 492L1000 505L860 490L770 455Z"/></mask>
      <linearGradient id="aniMsLG" gradientUnits="userSpaceOnUse" x1="0" y1="440" x2="0" y2="505"><stop offset="0" stop-color="#000"/><stop offset="1" stop-color="#fff"/></linearGradient>
      <mask id="aniMsLF" maskUnits="userSpaceOnUse" x="1290" y="400" width="400" height="267"><rect x="1300" y="400" width="380" height="267" rx="40" fill="url(#aniMsLG)" filter="url(#aniRatFeather)"/></mask>
      <mask id="aniMsLH" maskUnits="userSpaceOnUse" x="760" y="400" width="440" height="267"><rect x="790" y="400" width="400" height="267" rx="40" fill="url(#aniMsLG)" filter="url(#aniRatFeather)"/></mask>
      <clipPath id="aniMsB" clipPathUnits="userSpaceOnUse"><rect width="1480" height="667"/></clipPath>
      <clipPath id="aniMsH" clipPathUnits="userSpaceOnUse"><rect x="1430" width="570" height="667"/></clipPath>
      <clipPath id="aniTmB" clipPathUnits="userSpaceOnUse"><rect width="1312" height="862"/></clipPath>
      <clipPath id="aniTmT" clipPathUnits="userSpaceOnUse"><rect y="845" width="1312" height="400"/></clipPath>
      <clipPath id="aniTrB" clipPathUnits="userSpaceOnUse"><rect width="1199" height="980"/></clipPath>
      <clipPath id="aniTrT" clipPathUnits="userSpaceOnUse"><rect y="962" width="1199" height="400"/></clipPath>
      <radialGradient id="aniRatEyeG"><stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient>
      <mask id="aniRatEyeM" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><ellipse cx="928" cy="200" rx="30" ry="26" fill="url(#aniRatEyeG)"/></mask>
      <mask id="aniRatNT" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H1193V616H384V530H262L252 352H0Z"/></mask>
      <mask id="aniRatNTs" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H1193V616H384V530H262L236 436L212 428L204 404L222 382L252 352H0Z"/></mask>
      <clipPath id="aniRatB" clipPathUnits="userSpaceOnUse"><rect x="0" y="0" width="770" height="616"/></clipPath>
      <clipPath id="aniRatH" clipPathUnits="userSpaceOnUse"><path clip-rule="evenodd" d="M752 0H1193V616H752Z M784,152 794 123 815 114 839 123 851 152 849 195 837 216 802 216 787 195Z"/></clipPath>
      <clipPath id="aniRatEar" clipPathUnits="userSpaceOnUse"><polygon points="778,150 790,116 815,106 842,116 856,150 854,200 840,224 800,224 782,200"/></clipPath>
      <linearGradient id="aniRatTailG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e6c2a6"/><stop offset=".45" stop-color="#cf9f83"/><stop offset="1" stop-color="#a8735d"/></linearGradient>
      <mask id="aniRatNF" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H1193V398L1000 400L860 404L780 418L700 434L560 444L420 446L330 438L240 420L0 418Z"/></mask>
      <mask id="aniRatNTF" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H1193V398L1000 400L860 404L780 418L700 434L560 444L420 446L330 438L264 424L252 352H0Z"/></mask>
      <clipPath id="aniRatPaw" clipPathUnits="userSpaceOnUse"><rect x="372" y="440" width="176" height="72"/></clipPath>
      <clipPath id="aniRatNP" clipPathUnits="userSpaceOnUse"><path clip-rule="evenodd" d="M0 0H1193V616H0Z M372 440H548V512H372Z"/></clipPath>`;

  const memo = {};
  const once = (key, fn) => memo[key] || (memo[key] = fn());
  const TAILS = { rat: 'M-30 3 C-44 4 -52 12 -64 10 C-72 9 -76 14 -82 12', mouse: 'M-30 3 C-48 5 -58 -2 -70 5 C-80 10 -90 8 -96 14', top: 'M-20 0 C-30 3 -38 -3 -50 2 C-56 5 -60 2 -64 5' };

  // ---- side view. o: {sw (paw swelling 0..1), ink, kind:'rat'|'mouse', noTail, noFeet (caller poses the legs),
  //      headGroup (wrap the head in <g class="head"> so it can turn)}  Returns art only (no marks).
  // ---- side view. o: {sw (paw swelling 0..1), ink, kind:'rat'|'mouse', noTail, noFeet (caller poses the legs),
  //      headGroup (wrap the head in <g class="head"> so it can turn),
  //      life ('breath' = asleep or anaesthetised, 'none' = dead), rat only: tail ('rest' | 'straight' | 'up' | 'curl' |
  //      'droop' | {p0, dp, b0, db, A, L}), sway (0..1 tail movement)}  Returns art only (no marks).
  // The side-view rat is a real photograph of an albino Wistar rat (rat-side-photo.webp, 1193 x 616, made from
  // wistar_rat_side_view_transparent.png with the studio floor removed). RAT_MAP puts its eye on (34,-4.8) and its
  // body on the old silhouette (rump about -27, back -14.5, belly 15.5, feet 21, nose 46). The photo's own tail is
  // masked off and replaced by a posable tail in the photo's colours, so it can lie, hang, rise or curl and move.
  const RAT_MAP = 'translate(-50.82 -21.04) scale(.092 .082)';
  // The tail is modelled in 3D and drawn in side view: h = height above the floor, z = depth towards the viewer
  // (seen as a little lower on screen, like the photo's tail curling on the floor in front of the rat).
  // the root sits inside the rump, under the fur, so the tail grows out of the body instead of stopping short of it
  const RAT_TAIL_ROOT = [-20.5, 9.6], RAT_ROOT_IN = 9, RAT_FLOOR = 20.6, RAT_DEPTH = .17;
  // p0: pitch at the root (deg, + up), dp: pitch change per unit (deg); b0/db: turn on the floor towards the viewer
  // (deg, per unit); A: sway (deg); L: length
  const RAT_TAILS = {
    rest: { p0: -24, dp: -1.2, b0: 0, db: 1.25, A: 16, L: 62 },        // drops to the floor and lies in a loose curve
    straight: { p0: -3, dp: -.2, b0: 0, db: 0, A: 5, L: 62 },         // held out straight back (restrainer, tail vein)
    up: { p0: 58, dp: -1.75, b0: 0, db: 0, A: 6, L: 50, air: 1 },     // raised and arched over (Straub tail, alarm)
    curl: { p0: -32, dp: -2, b0: 8, db: 3.9, A: 10, L: 62 },          // curled round in front of the body
    droop: { p0: -78, dp: 0, b0: 0, db: 1.2, A: 8, L: 62 }            // hanging straight down, e.g. a rat being lifted
  };
  const ratTailPose = p => typeof p === 'object' && p ? { ...RAT_TAILS.rest, ...p } : RAT_TAILS[p] || RAT_TAILS.rest;
  // centre line of the tail on screen; t (s) and ph drive the sway, amp scales it (0 = still), lift raises the tip
  function ratTailPts(pose, t = 0, ph = 0, amp = 0, lift = 0) {
    const P = ratTailPose(pose), N = 36, L = (P.L || 62) + RAT_ROOT_IN, ds = L / N, R = Math.PI / 180;
    let x = RAT_TAIL_ROOT[0], h = RAT_FLOOR - RAT_TAIL_ROOT[1], z = 0, pitch = P.p0, turn = P.b0;
    const pts = [[x, RAT_TAIL_ROOT[1]]];
    for (let i = 1; i <= N; i++) {
      const s = i * ds, u = s / L, wave = amp * P.A * Math.pow(u, 1.3) * Math.sin(6.2832 * .45 * t - s * .1 + ph);
      // the hidden part inside the rump runs straight back; the pose starts where the tail leaves the body
      const out = s > RAT_ROOT_IN;
      if (out) { pitch += P.dp * ds; turn += P.db * ds; }
      // ease onto the floor instead of kinking: the closer to the floor, the flatter the descent
      // inside the rump the tail already points the way the pose leaves (so it runs on from the photo's own tail base)
      const pe = !out ? Math.max(-30, Math.min(12, P.p0)) : pitch < 0 ? pitch * Math.min(1, h / 7) : pitch;
      const pp = (pe + (P.air ? wave : 0)) * R, tt = (turn + wave) * R;
      x -= Math.cos(tt) * Math.cos(pp) * ds; z += Math.sin(tt) * Math.cos(pp) * ds; h += Math.sin(pp) * ds;
      if (h < 0) { h = 0; if (pitch < 0) pitch = 0; }
      let hh = h;
      if (u > .7 && lift) hh += lift * ((u - .7) / .3) ** 2 * 2.2;
      pts.push([x, RAT_FLOOR - hh + z * RAT_DEPTH]);
    }
    return pts;
  }
  // point and direction at fraction u along the tail (pose at rest), for scenes that sample from the tail
  function ratTailPoint(pose, u) {
    const p = ratTailPts(pose), i = Math.max(1, Math.min(p.length - 1, Math.round(u * (p.length - 1))));
    return { x: p[i][0], y: p[i][1], ang: Math.atan2(p[i][1] - p[i - 1][1], p[i][0] - p[i - 1][0]) * 57.2958 };
  }
  function ratTailD(all, from = 0, ws = 1) {
    const pts = all.slice(from), n0 = all.length - 1;
    // a rat's tail is thick and conical at the root (about a tenth of the body length), tapering to a fine, rounded tip
    const n = pts.length - 1, W = i => { const u = (i + from) / n0; return ws * (.5 + 4.1 * Math.pow(1 - u, 1.1)) / 2; };
    const N = pts.map((p, i) => { const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1; return [-dy / l, dx / l]; });
    const edge = (off, sc) => {
      const q = (i, sg) => `${f2(pts[i][0] + N[i][0] * W(i) * (off + sg * sc))} ${f2(pts[i][1] + N[i][1] * W(i) * (off + sg * sc))}`;
      // rounded tip: a small arc between the two sides at the end
      const tip = pts[n], tw = W(n) * sc;
      return 'M' + pts.map((_, i) => q(i, 1)).join('L') + `A${f2(tw)} ${f2(tw)} 0 0 1 ` + q(n, -1) + 'L' + pts.map((_, i) => q(n - i, -1)).join('L') + 'Z' + (tip ? '' : '');
    };
    // scales: fine rings every other point, fading towards the tip
    let rings = '';
    for (let i = 2; i < n - 1; i += 1) { const k = .82; rings += `M${f2(pts[i][0] + N[i][0] * W(i) * k)} ${f2(pts[i][1] + N[i][1] * W(i) * k)}L${f2(pts[i][0] - N[i][0] * W(i) * k)} ${f2(pts[i][1] - N[i][1] * W(i) * k)}`; }
    return [edge(0, 1), edge(.5, .5), edge(-.42, .3), rings];
  }
  // from: first point drawn (the front copy of a tail curling in front of the body starts outside the rump)
  const RAT_TAIL_FRONT_FROM = 8;
  function ratTailSVG(pose, from = 0, ws = 1) {
    const [b, sh, li, rg] = ratTailD(ratTailPts(pose), from, ws);
    // soft, rounded shading: a darker underside and a blurred highlight along the top, like the photo's tail
    return `<path class="tB" d="${b}" fill="#d9a98c"/><path class="tS" d="${sh}" fill="#a26c57" opacity=".38" filter="url(#aniSoft)"/><path class="tL" d="${li}" fill="#f7e0cf" opacity=".55" filter="url(#aniSoft)"/><path class="tR" d="${rg}" fill="none" stroke="#9a6552" stroke-width=".06" opacity=".16"/>`;
  }
  // A photo-style tail along any cubic path (from inside the rump outwards), for animals held in poses the floor-based
  // tail poses cannot make, e.g. one hanging from a hand. ws scales its width (a mouse's is .7 of a rat's).
  function photoTailSVG(d, ws = 1) {
    const n = (d.match(/-?\d*\.?\d+/g) || []).map(Number), P = [[n[0], n[1]]];
    for (let i = 2; i + 5 < n.length; i += 6) {
      const a = P[P.length - 1], b = [n[i], n[i + 1]], c = [n[i + 2], n[i + 3]], e = [n[i + 4], n[i + 5]];
      for (let s = 1; s <= 12; s++) { const t = s / 12, u = 1 - t; P.push([0, 1].map(j => u * u * u * a[j] + 3 * u * u * t * b[j] + 3 * u * t * t * c[j] + t * t * t * e[j])); }
    }
    const [b, sh, li, rg] = ratTailD(P, 0, ws);
    return `<path d="${b}" fill="#d9a98c"/><path d="${sh}" fill="#a26c57" opacity=".38" filter="url(#aniSoft)"/><path d="${li}" fill="#f7e0cf" opacity=".55" filter="url(#aniSoft)"/><path d="${rg}" fill="none" stroke="#9a6552" stroke-width=".06" opacity=".1"/>`;
  }
  // where the tail leaves the body: a soft shadow on the tail under the rump, and fur from the rump lying over its base
  const RAT_TAIL_EXIT = [-28.2, 10.6];
  const ratTailShadow = () => `<ellipse cx="${RAT_TAIL_EXIT[0] + .6}" cy="${RAT_TAIL_EXIT[1] + .3}" rx="2.6" ry="3.1" fill="#5b3a2c" opacity=".32" filter="url(#aniSoft)"/>`;
  // o.mouse: the same photograph reshaped into a Swiss albino mouse, in the same units (callers scale it by .47 like
  // the other mouse art): a rounder head with a shorter muzzle, big rounded ears, a larger eye, whiter fur, a thinner tail
  function ratSideArt(o) {
    // o.held: an animal lifted in the hand uses a copy of the photo without the studio-floor shadow between its feet
    const sw = o.sw || 0, file = o.held ? 'rat-side-photo-held' : 'rat-side-photo', url = `${BASE}${file}.webp?v=${ANI_VER}`, mouse = !!o.mouse, tone = mouse ? ' filter="url(#aniMouseTone)"' : '';
    if (!held.has(file)) { const im = new Image(); im.src = url; held.set(file, im); }
    // the photo's tail is always masked off (a posable tail replaces it); without feet the legs fade under the belly
    // a tail leaving downwards keeps the photo's own tail base (the real join with the fur) and runs on from it
    const stub = !o.noTail && !o.tailPath && !o.noFeet && ratTailPose(o.tail || 'rest').p0 < -10;
    const mask = o.noFeet ? 'aniRatNTF' : stub ? 'aniRatNTs' : 'aniRatNT';
    const img = (clip, extra = '') => `<g transform="${RAT_MAP}"><g mask="url(#${mask})">${sw && !o.noFeet ? '<g clip-path="url(#aniRatNP)">' : ''}<image width="1193" height="616" preserveAspectRatio="none" decoding="sync" href="${url}" clip-path="url(#${clip})"${extra}/>${sw && !o.noFeet ? '</g>' : ''}</g></g>`;
    const ear0 = `<g transform="${RAT_MAP}"><image width="1193" height="616" preserveAspectRatio="none" href="${url}" clip-path="url(#aniRatEar)"${tone}/></g>`;
    // the mouse keeps the photo's ear in its head and lays a bigger copy over it, feathered so no edge shows
    const ear = mouse ? `<g transform="translate(23.6 -3.6) scale(1.6 1.5) rotate(-6) translate(-23.6 3.6)"><g transform="${RAT_MAP}"><image width="1193" height="616" preserveAspectRatio="none" href="${url}" mask="url(#aniRatEarM)"${tone}/></g></g>` : ear0;
    // the mouse's head: narrowed about the neck (20, 0) so the muzzle is shorter, a little taller, with the eye enlarged
    const HEADT = 'translate(20 0) scale(.88 1.08) translate(-20 0)';
    const eyeBig = `<g transform="translate(34.6 -4.6) scale(1.5) translate(-34.6 4.6)"><g transform="${RAT_MAP}"><image width="1193" height="616" preserveAspectRatio="none" href="${url}" mask="url(#aniRatEyeM)"${tone}/></g></g>`;
    const wh = once('whR', () => whiskerPaint(WHISK_D(43, .7, 1, .62), .16));
    const tail = o.tailPath ? `<g${mouse ? ' filter="url(#aniMouseTail)"' : ''}>${photoTailSVG(o.tailPath, mouse ? .7 : 1)}</g>` : o.noTail ? '' : `<g class="lvTail" data-pose="${typeof o.tail === 'object' ? JSON.stringify(o.tail).replace(/"/g, '&quot;') : (o.tail || 'rest')}" data-sway="${o.sway ?? 1}" data-ws="${mouse ? .7 : 1}"${mouse ? ' filter="url(#aniMouseTail)"' : ''}>${ratTailSVG(o.tail || 'rest', 0, mouse ? .7 : 1)}</g>`;
    // swollen hind paw: the photo's own paw, enlarged about its centre (-8.5, 18.4), with inflamed colour
    const paw = sw && !o.noFeet ? `<g class="lvPaw" data-sw="${sw}"><g transform="translate(-8.5 18.4) scale(${f2(1 + sw * .5)} ${f2(1 + sw * .85)}) translate(8.5 -18.4)"><g transform="${RAT_MAP}"><image width="1193" height="616" preserveAspectRatio="none" href="${url}" clip-path="url(#aniRatPaw)"/></g></g><ellipse cx="-8.5" cy="18.6" rx="${f2(8 + sw * 3.6)}" ry="${f2(2.3 + sw * 1.9)}" fill="#d43f52" opacity="${f2(sw * .42)}" filter="url(#aniSoft)"/></g>` : '<g class="lvPaw" data-sw="0"></g>';
    // the tail always grows from under the rump fur (drawn behind the body); a tail curving round on the floor towards
    // the viewer also passes in front of the legs, so its outer part is drawn again in front
    const tailFront = !o.noTail && !o.tailPath && ratTailPose(o.tail || 'rest').db >= .5 ? `<g class="lvTailF" data-from="${RAT_TAIL_FRONT_FROM}" data-ws="${mouse ? .7 : 1}"${mouse ? ' filter="url(#aniMouseTail)"' : ''}>${ratTailSVG(o.tail || 'rest', RAT_TAIL_FRONT_FROM, mouse ? .7 : 1)}</g>` : '';
    // body and head are separate pieces of the same photo (overlapping at the neck), so the head can sniff and turn
    // origin's rodentLife breathes and blinks every .lvBreath; ratLife below adds the rat's own movements
    const live = o.life === 'none' ? '' : ` class="lvBreath lvRat" data-sp="${mouse ? 'mouse' : 'rat'}"${o.life ? ` data-life="${o.life}"` : ''}`;
    return `<g${live}>
        ${o.noShadow ? '' : `<ellipse cx="6" cy="${o.noFeet ? 17.5 : 21.5}" rx="34" ry="2.6" fill="#000" opacity=".26" filter="url(#aniBlur)"/>`}
        ${tail}${(o.noTail && !o.tailPath) || stub ? '' : ratTailShadow()}
        ${img('aniRatB', tone)}${tailFront}
        <g${o.headGroup ? ' class="head"' : ''}><g class="lvSniff">${mouse ? `<g transform="${HEADT}">${img('aniRatHM', tone)}${eyeBig}</g>` : img('aniRatH')}
          <g class="lvEar"><g class="lvEarS">${ear}</g></g>
          <ellipse class="lvLid" cx="${mouse ? 33.3 : 34.6}" cy="-4.6" rx="${mouse ? 3.6 : 2.7}" ry="${mouse ? 2.6 : 1.7}" fill="#efe4dd" opacity="0"/>
          <g class="lvWhisk"><g class="lvWhiskS" opacity=".4">${wh}</g></g>
        </g></g>
        ${paw}
        ${o.ink ? `<line x1="-16" y1="17" x2="-8" y2="17" stroke="#1e3a8a" stroke-width="1.1"/>` : ''}
        </g>`;
  }

  // ---- Swiss albino mouse, side view: a photograph (tools/animal-photos, mouse-side-r), drawn at its original 2000 x 667
  // pixel size and mapped so its eye is on (34, -4.8) and its feet on y 19.5, like the painted mouse before it (the
  // caller's .47 scale is applied here too). Rump at -32.5, back -13, belly 12, nose 45.5; the tail leaves the body at
  // MOUSE_TAIL_ROOT. o: noTail, tailPath (a pose's own tail, from inside the rump), noFeet, headGroup, life, noShadow, ink,
  // legs (the photo's own fore and hind legs as separate pieces, .legF and .legH, behind the body, for scenes that move them;
  // shoulder about (18, 8), hip about (-20, 8), paws on y 19.5).
  const MOUSE_MAP = 'matrix(.068 0 0 .068 -82.21 -21.73)', MOUSE_TAIL_ROOT = [-29, 5.2];
  function mouseSidePhoto(o) {
    const url = `${BASE}mouse-side.webp?v=${ANI_VER}`;
    if (!held.has('mouseSide')) { const im = new Image(); im.src = url; held.set('mouseSide', im); }
    const noTail = o.noTail || !!o.tailPath;
    const mask = o.noFeet ? (noTail ? 'aniMsNFT' : 'aniMsNF') : noTail ? 'aniMsNT' : '';
    const img = clip => `<g transform="${MOUSE_MAP}"><g${mask ? ` mask="url(#${mask})"` : ''}><image width="2000" height="667" preserveAspectRatio="none" decoding="sync" href="${url}"${clip ? ` clip-path="url(#${clip})"` : ''}/></g></g>`;
    const tail = o.tailPath ? `<g filter="url(#aniMouseTail)">${photoTailSVG(o.tailPath, .62)}</g>` : '';
    const lid = `<ellipse class="lvLid" cx="34" cy="-4.8" rx="1.7" ry="1.5" fill="#f3eeeb" opacity="0"/>`;
    const leg = (cls, clip) => `<g class="${cls}"><g transform="${MOUSE_MAP}"><image width="2000" height="667" preserveAspectRatio="none" decoding="sync" href="${url}" mask="url(#${clip})"/></g></g>`;
    // the hind legs sit behind the body; the fore legs are drawn in front so a paw raised to the mouth stays in view
    const legsBack = o.legs ? leg('legH', 'aniMsLH') : '', legsFront = o.legs ? leg('legF', 'aniMsLF') : '';
    const live = o.life === 'none' ? '' : ` class="lvBreath" data-sp="mouse"${o.life ? ` data-life="${o.life}"` : ''}`;
    return `<g transform="scale(.47)"><g${live}>
        ${o.noShadow ? '' : `<ellipse cx="6" cy="${o.noFeet ? 13 : 19.5}" rx="36" ry="2.6" fill="#000" opacity=".28" filter="url(#aniBlur)"/>`}
        ${tail}${legsBack}
        ${o.headGroup ? `${img('aniMsB')}${legsFront}<g class="head">${img('aniMsH')}${lid}</g>` : `${img('')}${legsFront}${lid}`}
        <g class="lvEar"></g><g class="lvWhisk"></g><g class="lvPaw" data-sw="0"></g>
        ${o.ink ? `<line x1="-19" y1="9" x2="-11" y2="9" stroke="#1e3a8a" stroke-width="1.1"/>` : ''}
        </g></g>`;
  }
  // Where a marking spot sits on the side-view photo mouse, in the caller's units (the .47-scaled side view): the spot
  // is kept on the fur, just under the back line, and not behind the rump. Returns the cx/cy attributes.
  const MOUSE_BACK = [[-15.3, -.5], [-13.1, -2.2], [-9.9, -4.6], [-6.7, -5.6], [-3.5, -6], [-.3, -5.8], [2.9, -4.7], [6.1, -4.1], [16, -3.8], [22, -1]];
  function mouseMark(x, y) {
    x = Math.max(-14, Math.min(20, x));
    let i = 0; while (i < MOUSE_BACK.length - 2 && x > MOUSE_BACK[i + 1][0]) i++;
    const [a, b] = [MOUSE_BACK[i], MOUSE_BACK[i + 1]], back = a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]);
    return `cx="${f2(x)}" cy="${f2(Math.max(y, back + 1.8))}"`;
  }
  function animalSideArt(o = {}) {
    if (o.kind !== 'mouse') return ratSideArt(o);
    if (!o.painted) return mouseSidePhoto(o);
    const kind = o.kind === 'mouse' ? 'mouse' : 'rat', mouse = kind === 'mouse', sc = mouse ? .47 : 1, sw = o.sw || 0;
    const earRot = mouse ? -12 : -20, earS = mouse ? 1.42 : .94, eR = mouse ? 1.06 : .84;
    const tail = o.noTail ? '' : once('tail' + kind, () => tailArt(TAILS[kind], mouse ? 4.2 : 3.6, mouse ? 1.2 : .95));
    const wh = once('wh', () => whiskerPaint(WHISK_D(41.6, 2.6, 1, 1), .24));
    const ax = -14, ay = 15;
    return `<g transform="scale(${sc})"><g class="lvBreath" data-sp="${kind}"${o.life ? ` data-life="${o.life}"` : ''}>
        ${o.noShadow ? '' : `<ellipse cx="2" cy="17" rx="${mouse ? 40 : 36}" ry="3.2" fill="#000" opacity=".3" filter="url(#aniBlur)"/>`}
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
  // ---- top views of the mouse and the rat: photographs taken from above (tools/animal-photos, mouse-top, rat-top),
  // turned so the head points to +x and fitted on the old renders' boxes; the tail is a separate piece of the same
  // photo inside .lvTail so the scenes can swing it about the rump
  const TOP_PHOTO = {
    mouse: { file: 'mouse-top-photo', w: 1312, h: 1199, map: 'matrix(0 .056 -.066 0 31.17 -36.4)', b: 'aniTmB', t: 'aniTmT' },
    rat: { file: 'rat-top-photo', w: 1199, h: 1312, map: 'matrix(0 .054 -.0582 0 30.81 -31.59)', b: 'aniTrB', t: 'aniTrT' }
  };
  function topPhoto(kind, clip) {
    const P = TOP_PHOTO[kind], url = `${BASE}${P.file}.webp?v=${ANI_VER}`;
    if (!held.has(P.file)) { const im = new Image(); im.src = url; held.set(P.file, im); }
    return `<g transform="${P.map}"><image width="${P.w}" height="${P.h}" preserveAspectRatio="none" decoding="sync" href="${url}" clip-path="url(#${P[clip]})"/></g>`;
  }
  function animalTopArt(o = {}) {
    const mouse = o.kind === 'mouse', render = mouse || o.kind === 'rat';
    if (render && !o.painted) {
      const k = mouse ? 'mouse' : 'rat', tail = o.noTail ? '' : topPhoto(k, 't'), body = topPhoto(k, 'b');
      return `<g transform="scale(.72)">
        <ellipse cx="1" cy="1.5" rx="${mouse ? 24 : 26}" ry="${mouse ? 11.5 : 12.5}" fill="#000" opacity=".24" filter="url(#aniBlur)"/>
        ${o.life === 'none' ? `${tail}${body}` : `<g class="lvTail">${tail}</g><g class="lvTop" data-sp="${k}"${o.life ? ` data-life="${o.life}"` : ''}>${body}</g><g class="lvWhiskT"></g>`}
        </g>`;
    }
    const tail = o.noTail ? '' : once(mouse ? 'tailTm' : 'tailT', () => tailArt(TAILS.top, mouse ? 2.2 : 2.7, .8));
    const wh = once('whT', () => whiskerPaint([-1, 1].map(s => [[3, 12, 4.4], [5.5, 15, 8], [8, 13.5, 11.5], [10, 11, 13.5]].map(([a, L, e], i) => `M${f2(25.2 - i * .7)} ${f2(s * (1.2 + i * .35))}Q${f2(25 + L * .55)} ${f2(s * (1.6 + a * .55))} ${f2(25 + L)} ${f2(s * (2 + e))}`).join('')).join(''), .17));
    return `<g transform="scale(.72)">
        ${render ? '<ellipse cx="2.4" cy="2" rx="25.5" ry="10.4" fill="#000" opacity=".26" filter="url(#aniBlur)"/>' : '<ellipse cx="0" cy="2.6" rx="24" ry="11" fill="#000" opacity=".26" filter="url(#aniBlur)"/>'}
        ${o.life === 'none' ? `${tail}${sprite(render ? 'top-' + o.kind : 'top')}${wh}` : `<g class="lvTail">${tail}</g><g class="lvTop" data-sp="${mouse ? 'mouse' : 'rat'}"${o.life ? ` data-life="${o.life}"` : ''}>${sprite(render ? 'top-' + o.kind : 'top')}</g><g class="lvWhiskT">${wh}</g>`}
        </g>`;
  }

  // ---- albino rabbit, front view. Units are pixels of the render, origin midway between the eyes. o: {body}
  function realRabbitHead(o = {}) {
    const wh = [[-1, -6, 96], [-1, 3, 112], [-1, 12, 104], [1, -6, 96], [1, 3, 112], [1, 12, 104]].map(([s, dy, l]) => `<path d="M${s * 34} ${158 + dy} Q${s * (34 + l * .6)} ${146 + dy * 1.6} ${s * (34 + l)} ${166 + dy * 3}" fill="none" stroke="#e9e2da" stroke-opacity=".8" stroke-width="1.1"/>`).join('');
    // a soft cast shadow keeps white fur readable on the pale scene backgrounds
    const cast = (cy, rx, ry) => `<ellipse cx="0" cy="${cy}" rx="${rx}" ry="${ry}" fill="#4a3a34" opacity=".34" filter="url(#realBlur)" transform="translate(4 10)"/>`;
    return `${o.body ? sprite('rbBody') : cast(62, 110, 186)}<g class="rbEarL">${sprite('rbEarL')}</g><g class="rbEarR">${sprite('rbEarR')}</g>${sprite('rbHead')}<radialGradient id="rbMuzzleG"><stop offset=".6" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient><mask id="rbMuzzleM"><ellipse cx="0" cy="158" rx="54" ry="48" fill="url(#rbMuzzleG)"/></mask><g class="rbNose"><g mask="url(#rbMuzzleM)">${sprite('rbHead')}</g></g><g class="rbWhisk">${wh}</g>`;
  }
  // One eye laid over the head so an experiment can still resize the pupil (pupilId is that hook).
  // The rabbit faces the viewer with its eyes on the sides of its head, so a round eye looks narrow.
  function realRabbitEye(cx, cy, r, pupilId, pupilR) {
    return `<g transform="translate(${cx} ${cy}) scale(.62 1)"><circle r="${r}" fill="#a9525f" opacity=".55"/>
        <circle ${pupilId ? `id="${pupilId}" ` : ''}r="${pupilR}" fill="#2a0510" opacity=".92"/>
        <circle cx="${f2(-r * .32)}" cy="${f2(-r * .36)}" r="${f2(r * .16)}" fill="#fff" opacity=".75"/></g>`;
  }
  // Each eye by side (-1 is the viewer's left), in head units: centre, then the two edges of the opening from top to bottom.
  const EYES = {
    '-1': { at: [-84, 3], a: [[-83, -19], [-91, -13], [-94.5, -3], [-94.5, 7], [-91, 17], [-84, 26]], b: [[-83, -19], [-77, -14], [-74, -4], [-74, 8], [-76, 19], [-84, 26]] },
    1: { at: [82.5, 3], a: [[81, -19], [75.5, -13], [73, -2], [73.5, 10], [76, 20], [81, 26]], b: [[81, -19], [87, -14], [91.5, -3], [92, 7], [89, 17], [81, 26]] }
  };
  function walkChain(ch, t) {
    let left = t * ch.reduce((n, p, i) => i ? n + Math.hypot(p[0] - ch[i - 1][0], p[1] - ch[i - 1][1]) : 0, 0);
    const out = [ch[0]];
    for (let i = 1; i < ch.length; i++) {
      const a = ch[i - 1], b = ch[i], d = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (left >= d) { out.push(b); left -= d; } else { out.push([a[0] + (b[0] - a[0]) * left / d, a[1] + (b[1] - a[1]) * left / d]); break; }
    }
    return out;
  }
  // Eyelid in head units, c 0 (open) to 1 (shut). Fur from the nose side of the eye closes over it, so the lid is
  // the animal's own coat. tag keeps the ids apart when one eye is drawn twice.
  function realRabbitLid(side, c, tag = '') {
    if (c <= 0) return '';
    const P = ([x, y]) => `${f2(x)} ${f2(y)}`, t = .05 + c * .85;
    const a = walkChain(EYES[side].a, t), b = walkChain(EYES[side].b, t), L = a[a.length - 1], R = b[b.length - 1];
    const Q = `Q${P([(L[0] + R[0]) / 2, (L[1] + R[1]) / 2 + 2.5])} ${P(R)}`, id = `rbLid${side < 0 ? 'L' : 'R'}${tag}`;
    const lid = `M${a.map(P).join('L')}${Q}L${b.slice(0, -1).reverse().map(P).join('L')}Z`;
    return `<g pointer-events="none"><filter id="${id}F" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation=".8"/></filter><mask id="${id}"><path d="${lid}" fill="#fff" filter="url(#${id}F)"/></mask>
        <g mask="url(#${id})"><g transform="translate(${side * 30} 0)">${sprite('rbBody')}</g><path d="${lid}" fill="#6f625e" opacity=".2"/></g>
        <path d="M${P(L)}${Q}" fill="none" stroke="#7a5a5c" stroke-width=".8" stroke-linecap="round" opacity=".6"/></g>`;
  }
  // A round magnified view of one eye, centred on (x, y) in the caller's scene. c is the lid, as above.
  function realRabbitEyeView(side, c, x, y, r, zoom = 4) {
    const [ex, ey] = EYES[side].at, id = `rbLoupe${side < 0 ? 'L' : 'R'}`;
    return `<clipPath id="${id}"><circle cx="${x}" cy="${y}" r="${r}"/></clipPath><circle cx="${x}" cy="${y}" r="${r}" fill="#fff"/>
        <g clip-path="url(#${id})"><g transform="translate(${x} ${y}) scale(${zoom}) translate(${-ex} ${-ey})">${sprite('rbBody')}${realRabbitLid(side, c, 'Z')}</g></g>
        <circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="#334155" stroke-width="3"/>`;
  }
  // A cut-out render with its studio shadow baked in pale. Multiplying makes that read as a shadow, but an SVG
  // blends only with its own content, so the caller must paint the bench behind this inside the same SVG.
  function realGuineaPig(transform) { return sprite('guineaPig', `style="mix-blend-mode:multiply"${transform ? ` transform="${transform}"` : ''}`); }
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

  // ---- Living motion. Visual only: nothing here reads or changes a recorded value.
  // data-life on an animal: absent = awake, "breath" = asleep or anaesthetised (slow breathing, nothing else).
  // Dead animals are drawn with life: 'none' and never reach this code. Animals are found afresh each step,
  // so scenes that redraw keep working. Slots are per position, so animals never move in unison.
  const stillMotion = !!(global.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  const TAU = 2 * Math.PI, BREATH_HZ = { mouse: 2.6, rat: 1.5 };
  const nowS = () => performance.now() / 1000;
  (function rodentLife() {
    if (stillMotion) return;
    const slots = { side: [], top: [] };
    const slot = (k, i) => slots[k][i] || (slots[k][i] = { ph: Math.random() * TAU, blinkAt: 2 + Math.random() * 8, blinkEnd: 0, burst: 0, burstAt: 1 + Math.random() * 5 });
    let clock = 0, last = null, since = 0, slowFor = 0, gap = 16, low = false;
    const twitch = s => { if (clock > s.burstAt) { s.burstAt = clock + 2 + Math.random() * 4; s.burst = 1; } s.burst *= .93; return s.burst * Math.sin(TAU * 9 * clock + s.ph); };
    const breath = (g, s, a) => { const asleep = g.dataset.life === 'breath', hz = (BREATH_HZ[g.dataset.sp] || 2) * (asleep ? .6 : 1); return { asleep, v: (1 + a * (asleep ? 1.4 : 1) * Math.sin(TAU * hz * clock + s.ph)).toFixed(4) }; };
    function sideView() {
      document.querySelectorAll('.lvBreath').forEach((g, i) => {
        const s = slot('side', i), b = breath(g, s, .018);
        if (!low) g.setAttribute('transform', `translate(0 16) scale(1 ${b.v}) translate(0 -16)`);   // about the feet, so the paws stay planted
        if (b.asleep) return;
        if (clock > s.blinkAt) { s.blinkAt = clock + 4 + Math.random() * 8; s.blinkEnd = clock + .12; }
        const lid = g.querySelector('.lvLid'), ear = g.querySelector('.lvEar'), wh = g.querySelector('.lvWhisk'), tw = twitch(s);
        if (lid) lid.setAttribute('opacity', clock < s.blinkEnd ? '1' : '0');
        if (ear) ear.setAttribute('transform', `rotate(${f2(3 * Math.sin(clock * .9 + s.ph) + tw * 5)} 23 -12)`);
        if (wh) wh.setAttribute('transform', `rotate(${f2(tw * 4)} 41 2.6)`);
      });
    }
    function topView() {
      document.querySelectorAll('.lvTop').forEach((g, i) => {
        const s = slot('top', i), b = breath(g, s, .02);
        if (!low) g.setAttribute('transform', `scale(1 ${b.v})`);                                     // the flanks widen as it breathes
        if (b.asleep) return;
        const tw = twitch(s), tail = g.parentNode.querySelector('.lvTail'), wh = g.parentNode.querySelector('.lvWhiskT');
        if (tail) tail.setAttribute('transform', `rotate(${f2(2.2 * Math.sin(clock * 1.1 + s.ph) + tw * 1.5)} -20 0)`);
        if (wh) wh.setAttribute('transform', `rotate(${f2(tw * 4)} 25 0)`);
      });
    }
    // The photo rat's own movements, on top of the breathing and blinks above: sniffing bouts with whisking, a quick
    // ear flick now and then, and a living tail (slow sway, tip twitches, an occasional flick). Asleep rats only breathe.
    const ratSlots = new WeakMap();
    function ratLife(dt) {
      const T = clock;
      document.querySelectorAll('.lvRat').forEach(r => {
        if (r.dataset.life) return;
        let s = ratSlots.get(r);
        if (!s) { s = { ph: Math.random() * TAU, sniffAt: T + .5 + Math.random() * 3, sniffEnd: 0, earAt: T + 2 + Math.random() * 6, earEnd: 0, flickAt: T + 3 + Math.random() * 6, flick: 0, twAt: T + 1 + Math.random() * 3, tw: 0 }; ratSlots.set(r, s); }
        if (T > s.sniffAt) { s.sniffEnd = T + .6 + Math.random() * 1.4; s.sniffAt = s.sniffEnd + 1.5 + Math.random() * 4.5; }
        const sniff = T < s.sniffEnd;
        const head = sniff ? 1.1 * Math.sin(TAU * 7 * T) + .6 : 1.4 * Math.sin(T * .7 + s.ph);
        const sn = r.querySelector('.lvSniff'); if (sn) sn.setAttribute('transform', `rotate(${f2(head)} 20 -0.5)`);
        const wk = r.querySelector('.lvWhiskS'); if (wk) wk.setAttribute('transform', `rotate(${f2(sniff ? 8 * Math.sin(TAU * 8 * T + 1) : 1.2 * Math.sin(T * 1.3 + s.ph))} 43 .7)`);
        if (T > s.earAt) { s.earEnd = T + .28; s.earAt = T + 2.5 + Math.random() * 7; }
        const ear = r.querySelector('.lvEarS'); if (ear) ear.setAttribute('transform', `rotate(${f2(T < s.earEnd ? -7 * Math.sin(Math.PI * (1 - (s.earEnd - T) / .28)) : 0)} 24.4 -3.3)`);
        const tl = r.querySelector('.lvTail');
        if (!tl) return;
        if (T > s.flickAt) { s.flickAt = T + 4 + Math.random() * 8; s.flick = 1; }
        if (T > s.twAt) { s.twAt = T + 1.2 + Math.random() * 3; s.tw = 1; }
        s.flick *= Math.pow(.2, dt); s.tw *= Math.pow(.05, dt);
        const sway = tl.dataset.sway === undefined ? 1 : +tl.dataset.sway;
        let pose = tl.dataset.pose; if (pose && pose[0] === '{') { try { pose = JSON.parse(pose); } catch (e) { pose = 'rest'; } }
        const pts = ratTailPts(pose, T, s.ph, sway * (1 + 2.2 * s.flick), sway * (1.6 * s.tw + 2.4 * s.flick) * (.6 + .4 * Math.sin(T * 9)));
        const paint = (g, from) => {
          const d = ratTailD(pts, from, +(g.closest('.lvTail,.lvTailF').dataset.ws || 1)), [b, sh, li, rg] = ['.tB', '.tS', '.tL', '.tR'].map(q => g.querySelector(q));
          if (b) { b.setAttribute('d', d[0]); sh.setAttribute('d', d[1]); li.setAttribute('d', d[2]); rg.setAttribute('d', d[3]); }
        };
        paint(tl, 0);
        const tf = r.querySelector('.lvTailF'); if (tf) paint(tf, +tf.dataset.from || 0);
      });
    }
    function frame(ts) {
      requestAnimationFrame(frame);
      if (last === null) last = ts;
      const dt = Math.min(.1, (ts - last) / 1000); last = ts;
      if (document.hidden) return;
      // Guardrail for low-spec lab PCs: if frames stay slow for 2 s, drop the breathing and run the small movements at 12 fps.
      gap += (dt * 1000 - gap) * .1;
      slowFor = gap > 40 ? slowFor + dt : 0;
      if (slowFor > 2) low = true;
      clock += dt; since += dt;
      if (since < (low ? 1 / 12 : 1 / 30)) return;
      const step = since; since = 0;
      if (typeof LiveRodent === 'undefined') sideView();                                               // Exp 4 and 21 drive their own side view
      topView();
      ratLife(step);
    }
    requestAnimationFrame(frame);
  })();

  // Rabbit and guinea pig: for scenes that redraw every frame, so these are called from the drawing code.
  // flinch 0..1 follows the reflex. It stays 0 when the eye is anaesthetised, so motion can't be mistaken for a response.
  function rabbitPose(flinch = 0) {
    if (stillMotion) return '';
    return `translate(0 ${f2(Math.sin(nowS() * TAU * .8) * 1.8 - flinch * 6)}) scale(${f2(1 - flinch * .012)})`;
  }
  const rb = { burst: 0, next: 2 };
  function animateRabbit(root, flinch = 0) {
    if (stillMotion) return;
    const t = nowS(), drift = 1.4 * Math.sin(t * .82) + .7 * Math.sin(t * 1.95);
    if (t > rb.next) { rb.next = t + 2 + Math.random() * 4; rb.burst = 1; }
    rb.burst *= .93;
    const tw = rb.burst * Math.sin(t * TAU * 9), set = (c, v) => root.querySelectorAll(c).forEach(g => g.setAttribute('transform', v));
    set('.rbEarL', `rotate(${f2(drift + tw * 2.5 - flinch * 7)} -66 -92)`);
    set('.rbEarR', `rotate(${f2(-drift * .8 - tw * 1.5 + flinch * 7)} 66 -92)`);
    set('.rbWhisk', `translate(0 ${f2(tw * 2.4)})`);
    set('.rbNose', `translate(0 ${f2(Math.sin(t * TAU * 4) * 2)})`);
  }
  // Resting guinea pig, about 84 breaths a minute. shiver is the panniculus reflex: the skin of the back jumps.
  function guineaPigPose(shiver) {
    if (stillMotion) return '';
    const t = nowS(), s = shiver ? 1 : 0;
    return `translate(${f2(509 + s * Math.sin(t * TAU * 21) * .9)} ${f2(200 + s * Math.cos(t * TAU * 17) * .6)}) scale(1 ${(1 + Math.sin(t * TAU * 1.4) * .012 + s * .006).toFixed(4)}) translate(-509 -200)`;
  }

  // Photo renders of a blue nitrile glove, cut out by tools/hand-sprites and laid over the animal a bench draws.
  // name: scruff | tail | hold. (x, y) is the top left corner and w the width, in the caller's units.
  const HAND_VER = 3, HAND_BASE = new URL('../img/hands/', document.currentScript.src).href;
  const HAND_SIZE = { scruff: [640, 415], tail: [640, 413], hold: [640, 434] };
  // The renders fade out at the wrist; a white lab-coat sleeve with a cuff is drawn over that fade so the glove ends in
  // an arm. Per render, in its pixels: where the cuff sits (x), the wrist's top and bottom there (t, b), which way the
  // forearm leaves (dir) and how its top and bottom edges run (dt, db: y change per pixel along the arm).
  const SLEEVE = {
    scruff: { x: 508, t: 6, b: 300, dir: 1, dt: -.06, db: .05 },
    hold: { x: 500, t: 70, b: 384, dir: 1, dt: .18, db: .02 },
    tail: { x: 62, t: 104, b: 404, dir: -1, dt: .22, db: .02 }
  };
  function sleeveArt(name, len) {
    const s = SLEEVE[name], L = len, d = s.dir, m = (s.t + s.b) / 2, id = 'hSl' + name;
    const X = u => f2(s.x + d * u);
    const top = u => s.t - 8 + s.dt * u - u * .05, bot = u => s.b + 8 + s.db * u + u * .05;
    const body = `M${X(0)} ${f2(top(0))} L${X(L)} ${f2(top(L))} L${X(L)} ${f2(bot(L))} L${X(0)} ${f2(bot(0))} Q${X(-20)} ${f2(m)} ${X(0)} ${f2(top(0))}Z`;
    const fold = (u0, u1, k, o) => `<path d="M${X(u0)} ${f2(top(u0) + (bot(u0) - top(u0)) * k)} Q${X((u0 + u1) / 2)} ${f2(top(u0) + (bot(u0) - top(u0)) * (k + .07))} ${X(u1)} ${f2(top(u1) + (bot(u1) - top(u1)) * k)}" stroke="#9aa5b1" stroke-opacity="${o}" stroke-width="5" fill="none" stroke-linecap="round" filter="url(#hSlBlur)"/>`;
    return `<defs><linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="0" y1="${f2(s.t)}" x2="0" y2="${f2(s.b)}"><stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#f4f6f8"/><stop offset=".85" stop-color="#d3d9e0"/><stop offset="1" stop-color="#b9c2cc"/></linearGradient>
        <linearGradient id="${id}F" gradientUnits="userSpaceOnUse" x1="${X(L * .55)}" y1="0" x2="${X(L)}" y2="0"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
        <mask id="${id}M" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="5000" height="5000"><rect x="-2000" y="-2000" width="5000" height="5000" fill="url(#${id}F)"/></mask>
        <filter id="hSlBlur" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4"/></filter></defs>
      <ellipse cx="${X(-4)}" cy="${f2(m + 6)}" rx="20" ry="${f2((s.b - s.t) / 2)}" fill="#1e3a8a" opacity=".32" filter="url(#hSlBlur)"/>
      <g mask="url(#${id}M)"><path d="${body}" fill="url(#${id})" stroke="#aab4bf" stroke-width="2"/>
        <path d="M${X(40)} ${f2(top(40) + 3)} Q${X(26)} ${f2(m)} ${X(40)} ${f2(bot(40) - 3)}" stroke="#a9b3be" stroke-width="2.4" fill="none"/>
        ${fold(70, L * .6, .3, .35)}${fold(120, L * .8, .62, .4)}${fold(60, L * .45, .82, .3)}
        <path d="M${X(10)} ${f2(top(10) + 10)} L${X(L)} ${f2(top(L) + 12)}" stroke="#fff" stroke-width="6" stroke-opacity=".9" fill="none" filter="url(#hSlBlur)"/></g>`;
  }
  // o.sleeve: length of the sleeve in render pixels (default 420); 0 leaves the render's own fade
  function handArt(name, x, y, w, attrs = '', o = {}) {
    const [pw, ph] = HAND_SIZE[name], url = `${HAND_BASE}${name}.webp?v=${HAND_VER}`;
    if (!held.has('hand-' + name)) { const im = new Image(); im.src = url; held.set('hand-' + name, im); }
    const img = `<image x="${f2(x)}" y="${f2(y)}" width="${f2(w)}" height="${f2(w * ph / pw)}" preserveAspectRatio="none" decoding="sync" ${attrs} href="${url}"/>`;
    const len = o.sleeve ?? 420;
    return len ? `${img}<g transform="translate(${f2(x)} ${f2(y)}) scale(${(w / pw).toFixed(5)})" pointer-events="none">${sleeveArt(name, len)}</g>` : img;
  }

  Object.assign(global, { handArt, tailArt, photoTailSVG, MOUSE_TAIL_ROOT, mouseMark, ANI_DEFS, animalSideArt, ratTailPoint, RAT_MAP, animalTopArt, realRabbitHead, realRabbitEye, realRabbitLid, realRabbitEyeView, rabbitPose, animateRabbit, guineaPigPose, realGuineaPig, realFrogBody, realFrogLeg, frogVentralArt, frogPlate, frogPlateUrl, openFrogAnatomy });
})(window);
