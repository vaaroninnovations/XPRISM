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
  const ANI_VER = 9;
  const BASE = new URL('../img/animals/', document.currentScript.src).href;
  const BOX = {
    'side-rat': [-38, -23, 50, 20], 'side-mouse': [-38, -23, 50, 20], earS: [16.5, -22, 30, -7.5],
    footH: [-23, 8, 3, 19], footHfar: [-23, 8, 3, 19], footF: [18, 9, 32, 19], footFfar: [18, 9, 32, 19],
    top: [-27, -16, 32, 16], 'top-rat': [-27, -16, 32, 16], 'top-mouse': [-27, -16, 32, 16],
    rbHead: [-152, -130, 152, 150], rbEar: [20, -244, 112, -70], rbBody: [-264, 84, 264, 256],
    guineaPig: [112, 28, 906, 412], frogBody: [428, 84, 572, 286], frogVen07: [96, 28, 564, 448], frogVen12: [330, 48, 670, 566]
  };

  const f2 = v => (Math.round(v * 100) / 100).toString();
  const lerp = (a, b, t) => a + (b - a) * t;

  // Each drawing is a plain <image>, which always repaints when its file arrives.
  // Holding a preloaded Image keeps the file in the browser's memory cache, so scenes
  // that rebuild their markup every frame reuse it instead of loading it again.
  const held = new Map();
  function sprite(name) {
    const b = BOX[name], url = `${BASE}${name}.webp?v=${ANI_VER}`;
    if (!held.has(name)) { const im = new Image(); im.src = url; held.set(name, im); }
    return `<image x="${b[0]}" y="${b[1]}" width="${b[2] - b[0]}" height="${b[3] - b[1]}" preserveAspectRatio="none" decoding="sync" href="${url}"/>`;
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
      <clipPath id="aniClipB"><rect x="-70" y="-40" width="97" height="80"/></clipPath><clipPath id="aniClipH"><rect x="24" y="-40" width="40" height="80"/></clipPath>
      <filter id="aniRatFeather" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="7"/></filter>
      <mask id="aniRatNT" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H1193V616H384V530H262L252 352H0Z"/></mask>
      <mask id="aniRatNTs" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H1193V616H384V530H262L236 436L212 428L204 404L222 382L252 352H0Z"/></mask>
      <clipPath id="aniRatB" clipPathUnits="userSpaceOnUse"><rect x="0" y="0" width="770" height="616"/></clipPath>
      <clipPath id="aniRatH" clipPathUnits="userSpaceOnUse"><rect x="752" y="0" width="441" height="616"/></clipPath>
      <clipPath id="aniRatEar" clipPathUnits="userSpaceOnUse"><polygon points="778,150 790,116 815,106 842,116 856,150 854,200 840,224 800,224 782,200"/></clipPath>
      <linearGradient id="aniRatTailG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e6c2a6"/><stop offset=".45" stop-color="#cf9f83"/><stop offset="1" stop-color="#a8735d"/></linearGradient>
      <mask id="aniRatNF" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M0 0H1193V398L1000 400L860 404L780 418L700 434L560 444L420 446L330 438L240 420L0 418Z"/></mask>
      <mask id="aniRatNTF" maskUnits="userSpaceOnUse" x="0" y="0" width="1193" height="616"><path fill="#fff" filter="url(#aniRatFeather)" d="M246 0H1193V398L1000 400L860 404L780 418L700 434L560 444L420 446L330 438L246 420Z"/></mask>
      <clipPath id="aniRatPaw" clipPathUnits="userSpaceOnUse"><rect x="372" y="440" width="176" height="72"/></clipPath>
      <clipPath id="aniRatNP" clipPathUnits="userSpaceOnUse"><path clip-rule="evenodd" d="M0 0H1193V616H0Z M372 440H548V512H372Z"/></clipPath>`;

  const memo = {};
  const once = (key, fn) => memo[key] || (memo[key] = fn());
  const TAILS = { rat: 'M-30 3 C-44 4 -52 12 -64 10 C-72 9 -76 14 -82 12', mouse: 'M-30 3 C-48 5 -58 -2 -70 5 C-80 10 -90 8 -96 14', top: 'M-20 0 C-30 3 -38 -3 -50 2 C-56 5 -60 2 -64 5' };

  // ---- side view. o: {sw (paw swelling 0..1), ink, kind:'rat'|'mouse', noTail, noFeet (caller poses the legs),
  //      headGroup (wrap the head in <g class="head"> so it can turn),
  //      rat only: tail ('rest' | 'straight' | 'up' | 'curl' | 'droop' | {a0, k, L}), sway (0..1 tail movement),
  //      still (no microanimation, e.g. anaesthetised)}  Returns art only (no marks).
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
  function ratTailD(all, from = 0) {
    const pts = all.slice(from), n0 = all.length - 1;
    // a rat's tail is thick and conical at the root (about a tenth of the body length), tapering to a fine, rounded tip
    const n = pts.length - 1, W = i => { const u = (i + from) / n0; return (.5 + 4.1 * Math.pow(1 - u, 1.1)) / 2; };
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
  function ratTailSVG(pose, from = 0) {
    const [b, sh, li, rg] = ratTailD(ratTailPts(pose), from);
    // soft, rounded shading: a darker underside and a blurred highlight along the top, like the photo's tail
    return `<path class="tB" d="${b}" fill="#d9a98c"/><path class="tS" d="${sh}" fill="#a26c57" opacity=".38" filter="url(#aniSoft)"/><path class="tL" d="${li}" fill="#f7e0cf" opacity=".55" filter="url(#aniSoft)"/><path class="tR" d="${rg}" fill="none" stroke="#9a6552" stroke-width=".06" opacity=".16"/>`;
  }
  // where the tail leaves the body: a soft shadow on the tail under the rump, and fur from the rump lying over its base
  const RAT_TAIL_EXIT = [-28.2, 10.6];
  const ratTailShadow = () => `<ellipse cx="${RAT_TAIL_EXIT[0] + .6}" cy="${RAT_TAIL_EXIT[1] + .3}" rx="2.6" ry="3.1" fill="#5b3a2c" opacity=".32" filter="url(#aniSoft)"/>`;
  function ratSideArt(o) {
    const sw = o.sw || 0, url = `${BASE}rat-side-photo.webp?v=${ANI_VER}`;
    if (!held.has('ratPhoto')) { const im = new Image(); im.src = url; held.set('ratPhoto', im); }
    // the photo's tail is always masked off (a posable tail replaces it); without feet the legs fade under the belly
    // a tail leaving downwards keeps the photo's own tail base (the real join with the fur) and runs on from it
    const stub = !o.noTail && !o.noFeet && ratTailPose(o.tail || 'rest').p0 < -10;
    const mask = o.noFeet ? 'aniRatNTF' : stub ? 'aniRatNTs' : 'aniRatNT';
    const img = (clip, extra = '') => `<g transform="${RAT_MAP}"><g mask="url(#${mask})">${sw && !o.noFeet ? '<g clip-path="url(#aniRatNP)">' : ''}<image width="1193" height="616" preserveAspectRatio="none" decoding="sync" href="${url}" clip-path="url(#${clip})"${extra}/>${sw && !o.noFeet ? '</g>' : ''}</g></g>`;
    const ear = `<g transform="${RAT_MAP}"><image width="1193" height="616" preserveAspectRatio="none" href="${url}" clip-path="url(#aniRatEar)"/></g>`;
    const wh = once('whR', () => whiskerPaint(WHISK_D(43, .7, 1, .62), .16));
    const tail = o.noTail ? '' : `<g class="lvTail" data-pose="${typeof o.tail === 'object' ? JSON.stringify(o.tail).replace(/"/g, '&quot;') : (o.tail || 'rest')}" data-sway="${o.sway ?? 1}">${ratTailSVG(o.tail || 'rest')}</g>`;
    // swollen hind paw: the photo's own paw, enlarged about its centre (-8.5, 18.4), with inflamed colour
    const paw = sw && !o.noFeet ? `<g class="lvPaw" data-sw="${sw}"><g transform="translate(-8.5 18.4) scale(${f2(1 + sw * .5)} ${f2(1 + sw * .85)}) translate(8.5 -18.4)"><g transform="${RAT_MAP}"><image width="1193" height="616" preserveAspectRatio="none" href="${url}" clip-path="url(#aniRatPaw)"/></g></g><ellipse cx="-8.5" cy="18.6" rx="${f2(8 + sw * 3.6)}" ry="${f2(2.3 + sw * 1.9)}" fill="#d43f52" opacity="${f2(sw * .42)}" filter="url(#aniSoft)"/></g>` : '<g class="lvPaw" data-sw="0"></g>';
    // the tail always grows from under the rump fur (drawn behind the body); a tail curving round on the floor towards
    // the viewer also passes in front of the legs, so its outer part is drawn again in front
    const tailFront = !o.noTail && ratTailPose(o.tail || 'rest').db >= .5 ? `<g class="lvTailF" data-from="${RAT_TAIL_FRONT_FROM}">${ratTailSVG(o.tail || 'rest', RAT_TAIL_FRONT_FROM)}</g>` : '';
    // body and head are separate pieces of the same photo (overlapping at the neck), so the head can sniff and turn
    return `<g class="lvBreath lvRat"${o.still ? ' data-still="1"' : ''}>
        <ellipse cx="6" cy="${o.noFeet ? 17.5 : 21.5}" rx="34" ry="2.6" fill="#000" opacity=".26" filter="url(#aniBlur)"/>
        ${tail}${o.noTail || stub ? '' : ratTailShadow()}
        ${img('aniRatB')}${tailFront}
        <g${o.headGroup ? ' class="head"' : ''}><g class="lvSniff">${img('aniRatH')}
          <g class="lvEar"><g class="lvEarS">${ear}</g></g>
          <ellipse class="lvLid" cx="34.6" cy="-4.6" rx="2.7" ry="1.7" fill="#efe4dd" opacity="0"/>
          <g class="lvWhisk"><g class="lvWhiskS" opacity=".4">${wh}</g></g>
        </g></g>
        ${paw}
        ${o.ink ? `<line x1="-16" y1="17" x2="-8" y2="17" stroke="#1e3a8a" stroke-width="1.1"/>` : ''}
        </g>`;
  }

  // ---- microanimation for the photo rat, shared by every page. Breathing, blinking, sniffing with whisking,
  // ear flicks and a living tail (slow sway, tip twitches, now and then a flick).
  // Pages that run their own animal loop (Exp 04, Exp 21) set window.ANI_PAGE_LIVE = true; they keep breathing,
  // blinks, ear and whisker swing, and this loop only adds the sniff, the inner ear flick, the whisking and the tail.
  // Calmer with data-sed="0..1" on an ancestor; frozen with data-still on the rat or an ancestor.
  const LIVE = new WeakMap();
  let liveT = 0, liveLast = null, liveOn = false;
  const reduceMotion = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } };
  function liveFrame(ts) {
    requestAnimationFrame(liveFrame);
    if (liveLast === null) liveLast = ts;
    const dt = Math.min(.05, (ts - liveLast) / 1000);
    if (dt < 1 / 40 || document.hidden) { if (document.hidden) liveLast = ts; return; }   // about 30-40 frames a second is plenty
    liveLast = ts; liveT += dt;
    const T = liveT, own = !!global.ANI_PAGE_LIVE, calm = reduceMotion();
    document.querySelectorAll('.lvRat').forEach(r => {
      let s = LIVE.get(r);
      if (!s) { s = { ph: Math.random() * 6.28, sniffAt: T + .5 + Math.random() * 3, sniffEnd: 0, blinkAt: T + 1 + Math.random() * 6, blinkEnd: 0, earAt: T + 2 + Math.random() * 6, earEnd: 0, flickAt: T + 3 + Math.random() * 6, flick: 0, twAt: T + 1 + Math.random() * 3, tw: 0 }; LIVE.set(r, s); }
      const still = r.hasAttribute('data-still') || !!r.closest('[data-still]');
      const host = r.closest('[data-sed]'), sed = host ? Math.min(1, +host.dataset.sed || 0) : 0;
      const act = still || calm ? 0 : 1 - sed;
      if (!own) {
        // breathing keeps going (gently) even when the rat is held still; only reduced motion stops it
        const f = 1.35 * (1 - .4 * sed), a = calm ? 0 : still ? .007 : .016 * (1 - .3 * sed);
        r.setAttribute('transform', `translate(0 21) scale(1 ${(1 + a * Math.sin(6.2832 * f * T + s.ph)).toFixed(4)}) translate(0 -21)`);
        if (T > s.blinkAt) { s.blinkAt = T + 3 + Math.random() * 8; s.blinkEnd = T + .13; }
        const lid = r.querySelector('.lvLid'), droop = sed > .5 ? Math.min(1, (sed - .5) * 2.2) : 0;
        if (lid) lid.setAttribute('opacity', (!calm && !still && T < s.blinkEnd ? 1 : droop).toFixed(2));
      }
      // sniffing bouts: small fast nods with whisking, then a pause; between bouts a slow look-around
      if (T > s.sniffAt) { s.sniffEnd = T + .6 + Math.random() * 1.4; s.sniffAt = s.sniffEnd + 1.5 + Math.random() * 4.5; }
      const sniff = T < s.sniffEnd ? 1 : 0;
      const head = act * (sniff ? 1.1 * Math.sin(6.2832 * 7 * T) + .6 : 1.4 * Math.sin(T * .7 + s.ph));
      const sn = r.querySelector('.lvSniff'); if (sn) sn.setAttribute('transform', `rotate(${head.toFixed(2)} 20 -0.5)`);
      const wk = r.querySelector('.lvWhiskS'); if (wk) wk.setAttribute('transform', `rotate(${(act * (sniff ? 8 * Math.sin(6.2832 * 8 * T + 1) : 1.2 * Math.sin(T * 1.3 + s.ph))).toFixed(2)} 43 .7)`);
      // ear flick: a quick backward twitch now and then
      if (T > s.earAt) { s.earEnd = T + .28; s.earAt = T + 2.5 + Math.random() * 7; }
      const ear = r.querySelector('.lvEarS'); if (ear) ear.setAttribute('transform', `rotate(${(T < s.earEnd ? -7 * act * Math.sin(Math.PI * (1 - (s.earEnd - T) / .28)) : 0).toFixed(2)} 24.4 -3.3)`);
      // tail: slow travelling sway, tip twitches, an occasional larger flick
      const tl = r.querySelector('.lvTail');
      if (tl) {
        if (T > s.flickAt) { s.flickAt = T + 4 + Math.random() * 8; s.flick = 1; }
        if (T > s.twAt) { s.twAt = T + 1.2 + Math.random() * 3; s.tw = 1; }
        s.flick *= Math.pow(.2, dt); s.tw *= Math.pow(.05, dt);
        const sway = (tl.dataset.sway === undefined ? 1 : +tl.dataset.sway) * act;
        let pose = tl.dataset.pose; if (pose && pose[0] === '{') { try { pose = JSON.parse(pose); } catch (e) { pose = 'rest'; } }
        const pts = ratTailPts(pose, T, s.ph, sway * (1 + 2.2 * s.flick), sway * (1.6 * s.tw + 2.4 * s.flick) * (.6 + .4 * Math.sin(T * 9)));
        const paint = (g, from) => {
          if (!g) return;
          const d = ratTailD(pts, from), [b, sh, li, rg] = ['.tB', '.tS', '.tL', '.tR'].map(q => g.querySelector(q));
          if (b) { b.setAttribute('d', d[0]); sh.setAttribute('d', d[1]); li.setAttribute('d', d[2]); rg.setAttribute('d', d[3]); }
        };
        paint(tl, 0);
        const tf = r.querySelector('.lvTailF'); if (tf) paint(tf, +tf.dataset.from || 0);
      }
    });
  }
  function startLive() { if (liveOn) return; liveOn = true; requestAnimationFrame(liveFrame); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', startLive); else startLive();
  function animalSideArt(o = {}) {
    if (o.kind !== 'mouse') return ratSideArt(o);
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

  // ---- top view (head to +x). o: {kind, noTail (caller draws its own)}
  function animalTopArt(o = {}) {
    const kind = o.kind === 'rat' ? 'rat' : (o.kind === 'mouse' ? 'mouse' : '');
    const spr = kind && BOX['top-' + kind] ? ('top-' + kind) : 'top';
    const tail = o.noTail ? '' : once('tailT' + kind, () => tailArt(TAILS.top, kind === 'mouse' ? 2.4 : 2.7, .8));
    const wh = once('whT', () => whiskerPaint([-1, 1].map(s => [[3, 12, 4.4], [5.5, 15, 8], [8, 13.5, 11.5], [10, 11, 13.5]].map(([a, L, e], i) => `M${f2(25.2 - i * .7)} ${f2(s * (1.2 + i * .35))}Q${f2(25 + L * .55)} ${f2(s * (1.6 + a * .55))} ${f2(25 + L)} ${f2(s * (2 + e))}`).join('')).join(''), .17));
    return `<g transform="scale(.72)">
        <ellipse cx="0" cy="2.6" rx="24" ry="11" fill="#000" opacity=".26" filter="url(#aniBlur)"/>
        ${tail}${sprite(spr)}${wh}
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
  function realGuineaPig() {
    const body = 'M138 232 C128 118 236 50 400 50 C540 50 666 66 750 112 C806 142 846 176 880 214 C884 220 884 226 880 232 C846 268 806 300 750 330 C666 376 540 392 400 390 C236 388 148 342 138 232Z';
    return `<path d="${body}" fill="#000" opacity=".3" filter="url(#realBlur)" transform="translate(6 16)"/>${sprite('guineaPig')}`;
  }
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

  Object.assign(global, { ANI_DEFS, animalSideArt, ratTailPoint, RAT_MAP, animalTopArt, realRabbitHead, realRabbitEye, realGuineaPig, realFrogBody, realFrogLeg, frogVentralArt });
})(window);
