/* Painter behind XPRISM's baked animal sprites (static/assets/img/animals/).
 * Runs in a browser: bake.html loads this file and saves each sprite. Re-run it
 * only when the art changes, then bump ANI_VER in static/assets/js/animal-art.js. */
(function (global) {
  'use strict';

  // ------------------------------------------------------------- utilities
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const sstep = (a, b, v) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
  const f2 = v => (Math.round(v * 100) / 100).toString();
  const gauss2 = (x, y, cx, cy, rx, ry) => Math.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2));

  function rng(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  function noise2(seed) {
    const S = 128, r = rng(seed), g = new Float32Array(S * S);
    for (let i = 0; i < g.length; i++) g[i] = r();
    return (x, y) => {
      const xi = Math.floor(x), yi = Math.floor(y), u = x - xi, v = y - yi, a = u * u * (3 - 2 * u), b = v * v * (3 - 2 * v);
      const at = (i, j) => g[(((j % S) + S) % S) * S + (((i % S) + S) % S)];
      return lerp(lerp(at(xi, yi), at(xi + 1, yi), a), lerp(at(xi, yi + 1), at(xi + 1, yi + 1), a), b);
    };
  }
  // closed Catmull-Rom through anatomical landmarks -> SVG path string
  function smoothClosed(p) {
    const n = p.length, q = i => p[((i % n) + n) % n];
    let d = `M${f2(p[0][0])} ${f2(p[0][1])}`;
    for (let i = 0; i < n; i++) {
      const a = q(i - 1), b = q(i), c = q(i + 1), e = q(i + 2);
      d += `C${f2(b[0] + (c[0] - a[0]) / 6)} ${f2(b[1] + (c[1] - a[1]) / 6)} ${f2(c[0] - (e[0] - b[0]) / 6)} ${f2(c[1] - (e[1] - b[1]) / 6)} ${f2(c[0])} ${f2(c[1])}`;
    }
    return d + 'Z';
  }
  // exact Euclidean distance transform (Felzenszwalb & Huttenlocher)
  function edt(inside, W, H) {
    const INF = 1e12, D = new Float64Array(W * H), M = Math.max(W, H), v = new Int32Array(M), z = new Float64Array(M + 1), f = new Float64Array(M), o = new Float64Array(M);
    for (let i = 0; i < D.length; i++) D[i] = inside[i] ? INF : 0;
    const pass = n => {
      let k = 0; v[0] = 0; z[0] = -INF; z[1] = INF;
      for (let q = 1; q < n; q++) {
        let s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]);
        while (s <= z[k]) { k--; s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]); }
        k++; v[k] = q; z[k] = s; z[k + 1] = INF;
      }
      k = 0;
      for (let q = 0; q < n; q++) { while (z[k + 1] < q) k++; o[q] = (q - v[k]) * (q - v[k]) + f[v[k]]; }
    };
    for (let x = 0; x < W; x++) { for (let y = 0; y < H; y++) f[y] = D[y * W + x]; pass(H); for (let y = 0; y < H; y++) D[y * W + x] = o[y]; }
    for (let y = 0; y < H; y++) { for (let x = 0; x < W; x++) f[x] = D[y * W + x]; pass(W); for (let x = 0; x < W; x++) D[y * W + x] = o[x]; }
    const out = new Float32Array(W * H);
    for (let i = 0; i < out.length; i++) out[i] = Math.sqrt(D[i]);
    return out;
  }
  function boxBlur(a, W, H, r) {
    const t = new Float32Array(a.length), w = 2 * r + 1;
    for (let y = 0; y < H; y++) { let s = 0; for (let x = -r; x <= r; x++) s += a[y * W + clamp(x, 0, W - 1)]; for (let x = 0; x < W; x++) { t[y * W + x] = s / w; s += a[y * W + Math.min(W - 1, x + r + 1)] - a[y * W + Math.max(0, x - r)]; } }
    for (let x = 0; x < W; x++) { let s = 0; for (let y = -r; y <= r; y++) s += t[clamp(y, 0, H - 1) * W + x]; for (let y = 0; y < H; y++) { a[y * W + x] = s / w; s += t[Math.min(H - 1, y + r + 1) * W + x] - t[Math.max(0, y - r) * W + x]; } }
  }

  function newCanvas(box, k) {
    const c = document.createElement('canvas');
    c.width = Math.ceil((box[2] - box[0]) * k); c.height = Math.ceil((box[3] - box[1]) * k);
    const ctx = c.getContext('2d');
    ctx.setTransform(k, 0, 0, k, -box[0] * k, -box[1] * k);
    return { c, ctx };
  }

  // ------------------------------------------------------------- fur painter
  /* o: box, k (px/unit), path, round (body radius, units), bumps [[x,y,rx,ry,height]...],
   *    flow(x,y)->[dx,dy], len(x,y)->units, density (hairs/unit^2), seed,
   *    ramp [[r,g,b] deep, mid, lite], tint(x,y)->[dr,dg,db] optional,
   *    under(ctx), over(ctx), hairW (units) */
  function paintFur(o) {
    const { box, k } = o, { c, ctx } = newCanvas(box, k), W = c.width, H = c.height;
    const X = i => box[0] + i / k, Y = j => box[1] + j / k;
    if (o.under) { ctx.save(); o.under(ctx); ctx.restore(); }

    // 1. silhouette -> height field
    const mc = document.createElement('canvas'); mc.width = W; mc.height = H;
    const mx = mc.getContext('2d', { willReadFrequently: true });
    mx.setTransform(k, 0, 0, k, -box[0] * k, -box[1] * k); (o.paths || [o.path]).forEach(p => mx.fill(new Path2D(p)));
    const al = mx.getImageData(0, 0, W, H).data, inside = new Uint8Array(W * H);
    for (let i = 0; i < inside.length; i++) inside[i] = al[i * 4 + 3] > 127 ? 1 : 0;
    const d = edt(inside, W, H), R = o.round * k, h = new Float32Array(W * H);
    for (let i = 0; i < h.length; i++) if (inside[i]) { const t = 1 - Math.min(d[i] / R, 1); h[i] = Math.sqrt(Math.max(0, 1 - t * t)) * R; }
    boxBlur(h, W, H, Math.max(1, Math.round(k * .9))); boxBlur(h, W, H, Math.max(1, Math.round(k * .9)));
    for (let j = 0; j < H; j += 1) for (let i = 0; i < W; i++) {
      const q = j * W + i; if (!inside[q]) continue;
      let v = o.relief ? o.relief(X(i), Y(j)) : 0; for (const b of o.bumps || []) v += b[4] * gauss2(X(i), Y(j), b[0], b[1], b[2], b[3]);
      h[q] += v * k;
    }
    boxBlur(h, W, H, Math.max(1, Math.round(k * .35)));

    // 2. light it
    const Lv = o.light || [-.28, -.78, .56], Ln = Math.hypot(...Lv), L = Lv.map(v => v / Ln);
    const shade = new Float32Array(W * H), nx = new Float32Array(W * H), ny = new Float32Array(W * H);
    const mott = noise2((o.seed || 1) + 5);
    for (let j = 1; j < H - 1; j++) for (let i = 1; i < W - 1; i++) {
      const q = j * W + i; if (!inside[q]) continue;
      const gx = (h[q + 1] - h[q - 1]) / 2, gy = (h[q + W] - h[q - W]) / 2, n = Math.hypot(gx, gy, 1), ax = -gx / n, ay = -gy / n, az = 1 / n;
      nx[q] = ax; ny[q] = ay;
      const dif = clamp((ax * L[0] + ay * L[1] + az * L[2] + .42) / 1.42), sky = clamp(.5 - ay * .5);
      const ao = sstep(0, R * .34, d[q]) * .1 + .9;
      shade[q] = clamp((.1 + dif * .78 + sky * .2) * ao + (mott(X(i) * .55, Y(j) * .55) - .5) * .05);
    }

    // colour ramp, pre-computed for speed
    const LV = 96, rgb = v => { const [a, b, e] = o.ramp, t = clamp(v); const [p, q, s] = t < .55 ? [a, b, t / .55] : [b, e, (t - .55) / .45]; return [lerp(p[0], q[0], s), lerp(p[1], q[1], s), lerp(p[2], q[2], s)]; };
    const css = Array.from({ length: LV + 1 }, (_, i) => { const [r, g, b] = rgb(i / LV); return `rgb(${r | 0},${g | 0},${b | 0})`; });

    // 3. undercoat
    const bc = document.createElement('canvas'); bc.width = W; bc.height = H;
    const bx = bc.getContext('2d'), im = bx.createImageData(W, H), px = im.data;
    for (let q = 0; q < W * H; q++) {
      if (!inside[q]) continue;
      let [r, g, b] = rgb(shade[q] - .05); const p = q * 4;
      if (o.albedo) {
        const x = X(q % W), y = Y((q / W) | 0), A = o.albedo(x, y, shade[q], d[q] / k), lit = (o.litMin || .4) + shade[q] * (o.litGain || .95);
        let sp = 0;
        if (o.spec) { const m = (mott(x * 3, y * 3) - .5) * .3, ax = nx[q] + m, ay = ny[q] - m, az = Math.sqrt(Math.max(.01, 1 - ax * ax - ay * ay)), hx = L[0], hy = L[1], hz = L[2] + 1, hn = Math.hypot(hx, hy, hz); sp = o.spec * Math.pow(clamp((ax * hx + ay * hy + az * hz) / hn), o.specP || 38) * 255; }
        r = Math.min(255, A[0] * lit + sp); g = Math.min(255, A[1] * lit + sp); b = Math.min(255, A[2] * lit + sp);
      }
      px[p] = r; px[p + 1] = g; px[p + 2] = b; px[p + 3] = 255 * sstep(0, k * .9, d[q]);
    }
    bx.putImageData(im, 0, 0);
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(bc, 0, 0); ctx.restore();

    if (o.hair === false) { if (o.over) { ctx.save(); o.over(ctx); ctx.restore(); } return { canvas: c, box }; }

    // 4. hair, in three coats
    const r = rng(o.seed || 1), nA = noise2((o.seed || 1) + 11), nB = noise2((o.seed || 1) + 23);
    let area = 0; for (let q = 0; q < inside.length; q++) area += inside[q];
    const N = Math.round(area / (k * k) * (o.density || 16));
    const coats = [[.5, .72, -.11, .62, 1.15], [.33, 1, -.03, .78, 1], [.17, 1.28, .09, .82, .72]];
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
    const hw = (o.hairW || .2) * k;
    for (const [frac, lenF, tone, alpha, wF] of coats) {
      const cnt = Math.round(N * frac), roots = [];
      while (roots.length < cnt) {
        const i = 2 + (r() * (W - 4)) | 0, j = 2 + (r() * (H - 4)) | 0, q = j * W + i;
        if (inside[q]) roots.push(q);
      }
      const ord = o.order || ((x, y) => x);
      const keyed = roots.map(q => [ord(X(q % W), Y((q / W) | 0)) + r() * .8, q]);
      keyed.sort((a, b) => a[0] - b[0]);
      ctx.globalAlpha = alpha;
      for (const [, q] of keyed) {
        const i = q % W, j = (q / W) | 0, x = X(i), y = Y(j);
        let [dx, dy] = o.flow(x, y);
        const dn = Math.hypot(dx, dy) || 1; dx /= dn; dy /= dn;
        const edge = 1 - sstep(0, k * 2.4, d[q]), en = Math.hypot(nx[q], ny[q]) || 1;
        const push = o.edge === undefined ? .75 : o.edge; dx += (nx[q] / en) * edge * push; dy += (ny[q] / en) * edge * push;
        const swirl = (nA(x * .3, y * .3) - .5) * 1.25 + (r() - .5) * .34, cs = Math.cos(swirl), sn = Math.sin(swirl);
        const ux = dx * cs - dy * sn, uy = dx * sn + dy * cs, un = Math.hypot(ux, uy) || 1, tx = ux / un, ty = uy / un;
        const len = o.len(x, y) * lenF * (.68 + r() * .62) * k, bend = (r() - .5) * .34 * len;
        const px_ = -ty, py_ = tx, w = hw * wF * (.75 + r() * .5), mx_ = i + tx * len * .5 + px_ * bend, my_ = j + ty * len * .5 + py_ * bend;
        ctx.beginPath(); ctx.moveTo(i + px_ * w * .5, j + py_ * w * .5);
        ctx.quadraticCurveTo(mx_ + px_ * w * .3, my_ + py_ * w * .3, i + tx * len, j + ty * len);
        ctx.quadraticCurveTo(mx_ - px_ * w * .3, my_ - py_ * w * .3, i - px_ * w * .5, j - py_ * w * .5);
        ctx.closePath();
        const clump = (nB(x * .62, y * 1.1) - .5) * .2;
        ctx.fillStyle = css[Math.round(clamp(shade[q] + tone + clump + (r() - .5) * .05) * LV)];
        ctx.fill();
      }
    }
    ctx.restore();
    if (o.over) { ctx.save(); o.over(ctx); ctx.restore(); }
    return { canvas: c, box };
  }


  // ------------------------------------------------------------- albino rodent anatomy
  const RAMP = [[156, 140, 132], [229, 219, 210], [255, 253, 249]];
  const SIDE_PTS = {
    rat: [[46, 1.4], [44.6, -.9], [41, -3.6], [37, -7.1], [32, -10], [25, -12], [15, -14.2], [2, -16.2], [-12, -16.9], [-24, -13.6], [-31.4, -6], [-33, 3], [-30.4, 10.2], [-24, 14.2], [-14, 15], [-5.4, 13], [5, 11.8], [14, 11.8], [18.4, 13], [21.6, 14.4], [25, 13.2], [27.4, 9.6], [32.4, 8.2], [39, 6.3], [44, 4.5]],
    mouse: [[45.4, 1.3], [44, -1.2], [41, -4.4], [37.4, -8.2], [32, -11.4], [25, -13], [15, -15], [2, -16.8], [-12, -17.1], [-24, -13.6], [-31.4, -6], [-33, 3], [-30.4, 10.2], [-24, 14.2], [-14, 15], [-5.4, 13.2], [5, 12.2], [14, 12.4], [18.4, 13.2], [21.6, 14.4], [25, 13.4], [27.8, 10.2], [32.8, 8.8], [39, 6.7], [43.6, 4.4]]
  };
  const SIDE_BUMPS = [[-17, 3, 11.5, 10.5, 3.6], [-4.5, 5, 2.8, 11, -1.2], [16, 3, 7, 8.5, 2.4], [24, 1, 2.6, 8, -.7], [33, 3.2, 5.5, 4.2, 1.2], [41.2, 2.5, 3.2, 2.4, 1.5], [34, -4.8, 3.1, 2.7, -1.4], [6, -1, 11, 7, .8]];
  function flowSide(x, y) {
    let dx = -1, dy = .08 + y * .016;
    if (x > 27) { const t = sstep(27, 37, x); dy = lerp(dy, (y + 2.4) * .05 - .06, t); }
    if (x < 8) dy += clamp((y + 3) / 15) * .85 * sstep(8, -8, x);
    if (x < -22) dy += clamp((y + 10) / 18) * .3;
    return [dx, dy];
  }
  function lenSide(x, y) {
    const face = sstep(44, 27, x), low = 1 - clamp((y - 4) / 14) * .35;
    return lerp(.5, 1.75, face) * low;
  }
  function pinkBlush(ctx, x, y, r, a) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(232,150,152,${a})`); g.addColorStop(1, 'rgba(232,150,152,0)');
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
  }
  function paintMuzzle(ctx, kind) {
    const m = kind === 'mouse', nx = m ? 45.3 : 45.8, ny = 1.3;
    ctx.save(); ctx.globalCompositeOperation = 'source-atop'; pinkBlush(ctx, 42.4, 2.2, 6, .34); pinkBlush(ctx, 34, -4.8, 4.4, .2); ctx.restore();
    ctx.fillStyle = 'rgba(140,108,102,.5)';
    [[39, 2.1], [40.6, 1.3], [42.2, .9], [39.4, 3.3], [41, 2.7], [42.6, 2.2], [40, 4.4], [41.8, 3.8], [43.2, 3.2]].forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x, y, .14, 0, 7); ctx.fill(); });
    ctx.strokeStyle = 'rgba(112,78,78,.75)'; ctx.lineWidth = .2; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(nx - .9, ny + 1.5); ctx.quadraticCurveTo(nx - 2.8, ny + 3.2, nx - 6.2, ny + 3.5); ctx.stroke();
    ctx.strokeStyle = 'rgba(214,160,160,.8)'; ctx.lineWidth = .18;
    ctx.beginPath(); ctx.moveTo(nx - .8, ny + 1.9); ctx.quadraticCurveTo(nx - 2.4, ny + 3.5, nx - 4.6, ny + 3.8); ctx.stroke();
    const g = ctx.createRadialGradient(nx - .5, ny - .5, .1, nx, ny, 2);
    g.addColorStop(0, '#f6c6cc'); g.addColorStop(.55, '#df97a5'); g.addColorStop(1, '#b56a7b');
    ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(nx, ny, 1.55, 1.3, .28, 0, 7); ctx.fill();
    ctx.fillStyle = '#6a2a39'; ctx.beginPath(); ctx.ellipse(nx + .7, ny - .1, .26, .5, .5, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,.65)'; ctx.beginPath(); ctx.ellipse(nx - .5, ny - .68, .34, .16, -.3, 0, 7); ctx.fill();
  }
  function sideBody(kind) {
    const m = kind === 'mouse';
    return paintFur({
      box: [-38, -23, 50, 20], k: 10, path: smoothClosed(SIDE_PTS[kind]), round: 14, bumps: SIDE_BUMPS,
      flow: flowSide, len: m ? (x, y) => lenSide(x, y) * 1.35 : lenSide, density: m ? 22 : 30, seed: m ? 41 : 17, ramp: RAMP, hairW: m ? .22 : .15, edge: .14,
      over: ctx => paintMuzzle(ctx, kind)
    });
  }
  function earSide() {
    const box = [16.5, -22, 30, -7.5], { c, ctx } = newCanvas(box, 26);
    const P = new Path2D(smoothClosed([[20.2, -9], [18.5, -12.8], [18.7, -16.8], [21, -20], [24.4, -20.6], [27.2, -18], [28.2, -13.6], [26.8, -9.4], [23.5, -8.2]]));
    const g = ctx.createRadialGradient(23.2, -13, .8, 23.3, -14, 7.4);
    g.addColorStop(0, '#dd98a6'); g.addColorStop(.42, '#ecb6bf'); g.addColorStop(.82, '#f1cbcd'); g.addColorStop(1, '#efd9d3');
    ctx.fillStyle = g; ctx.fill(P);
    ctx.save(); ctx.clip(P);
    const con = ctx.createRadialGradient(23.6, -9.4, .2, 23.6, -10, 5.4);
    con.addColorStop(0, 'rgba(122,56,74,.66)'); con.addColorStop(1, 'rgba(122,56,74,0)'); ctx.fillStyle = con; ctx.fillRect(16, -22, 14, 15);
    ctx.lineCap = 'round';
    [[23.3, -9.5, 21.8, -13.4, 20.8, -18, .13], [23.9, -9.5, 24.2, -13.2, 24.8, -18.4, .11], [22.6, -12.2, 21.2, -13.4, 19.8, -14.6, .06], [24.1, -13.2, 25.6, -14.2, 26.8, -15.4, .06]].forEach(([a, b, e, f, x, y, w]) => { ctx.strokeStyle = 'rgba(176,74,96,.26)'; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(a, b); ctx.quadraticCurveTo(e, f, x, y); ctx.stroke(); });
    ctx.strokeStyle = 'rgba(140,84,98,.3)'; ctx.lineWidth = .36; ctx.beginPath(); ctx.moveTo(26.6, -11); ctx.quadraticCurveTo(26.2, -16, 23.8, -18.6); ctx.stroke();
    ctx.restore();
    ctx.strokeStyle = 'rgba(250,236,230,.8)'; ctx.lineWidth = .3; ctx.stroke(P);
    const r = rng(77); ctx.lineWidth = .07; ctx.strokeStyle = 'rgba(250,242,236,.75)';
    for (let i = 0; i < 90; i++) { const t = r(), x = 19.5 + t * 7, y = -9 + r() * 1.6; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + (r() - .5) * .7, y - .7 - r() * 1); ctx.stroke(); }
    return { canvas: c, box };
  }
  function digit(ctx, x0, y0, x1, y1, w, far) {
    const n = Math.hypot(x1 - x0, y1 - y0), px = -(y1 - y0) / n, py = (x1 - x0) / n;
    ctx.beginPath(); ctx.moveTo(x0 + px * w, y0 + py * w); ctx.quadraticCurveTo((x0 + x1) / 2 + px * w * .7, (y0 + y1) / 2 + py * w * .7, x1 + px * w * .42, y1 + py * w * .42);
    ctx.quadraticCurveTo(x1 + (x1 - x0) / n * w * .7, y1 + (y1 - y0) / n * w * .7, x1 - px * w * .42, y1 - py * w * .42);
    ctx.quadraticCurveTo((x0 + x1) / 2 - px * w * .7, (y0 + y1) / 2 - py * w * .7, x0 - px * w, y0 - py * w); ctx.closePath(); ctx.fill();
    ctx.save(); ctx.strokeStyle = far ? 'rgba(122,70,80,.34)' : 'rgba(136,76,88,.34)'; ctx.lineWidth = .09;
    [.45, .74].forEach(t => { const x = lerp(x0, x1, t), y = lerp(y0, y1, t); ctx.beginPath(); ctx.moveTo(x + px * w * .6, y + py * w * .6); ctx.lineTo(x - px * w * .6, y - py * w * .6); ctx.stroke(); });
    ctx.restore();
    ctx.save(); ctx.fillStyle = '#f4e7d6'; ctx.beginPath(); ctx.moveTo(x1 + px * w * .3, y1 + py * w * .3); ctx.lineTo(x1 + (x1 - x0) / n * .75, y1 + (y1 - y0) / n * .75 + .1); ctx.lineTo(x1 - px * w * .3, y1 - py * w * .3); ctx.closePath(); ctx.fill(); ctx.restore();
  }
  function feet(which, far) {
    const hind = which === 'hind', box = hind ? [-23, 8, 3, 19] : [18, 9, 32, 19], { c, ctx } = newCanvas(box, 26);
    const skin = (y0, y1) => { const g = ctx.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, far ? '#d9c7c3' : '#f6ebe5'); g.addColorStop(.42, far ? '#d9a3ab' : '#f2c2c8'); g.addColorStop(1, far ? '#b5727f' : '#d58d9b'); return g; };
    if (hind) {
      ctx.fillStyle = skin(10.5, 17.2);
      ctx.beginPath(); ctx.moveTo(-20.6, 10.8); ctx.quadraticCurveTo(-22, 15, -20.2, 16.6); ctx.quadraticCurveTo(-13, 17.5, -6.2, 17); ctx.quadraticCurveTo(-5.4, 15.2, -7.4, 14.2); ctx.quadraticCurveTo(-12, 12.4, -15, 10.4); ctx.closePath(); ctx.fill();
      ctx.fillStyle = skin(13.6, 17.4);
      digit(ctx, -7.8, 16.2, -1.2, 16.9, .62, far); digit(ctx, -7.6, 15.5, -1.8, 15.5, .58, far); digit(ctx, -8.2, 14.9, -3.4, 14.2, .52, far);
    } else {
      ctx.fillStyle = skin(10.5, 17.2);
      ctx.beginPath(); ctx.moveTo(20.4, 10.6); ctx.quadraticCurveTo(20.4, 14, 21.4, 16.7); ctx.quadraticCurveTo(24, 17.4, 26, 16.7); ctx.quadraticCurveTo(25.8, 14.8, 24.8, 13.4); ctx.quadraticCurveTo(24.4, 12, 24.4, 10.6); ctx.closePath(); ctx.fill();
      ctx.fillStyle = skin(14.2, 17.4);
      digit(ctx, 25, 16.3, 29.4, 17, .42, far); digit(ctx, 25.2, 15.7, 29.8, 15.8, .4, far); digit(ctx, 24.9, 15.1, 28.6, 14.5, .36, far);
    }
    return { canvas: c, box };
  }

  // top view, head at +x; keeps the extents of the original art
  function topBody() {
    const pts = [[27, 0], [25.6, 1.5], [22.6, 3.3], [18.6, 4.9], [14.6, 5.5], [11.6, 6.3], [7, 8.3], [1, 9], [-6, 9.1], [-13, 9.9], [-18.2, 7.6], [-20.5, 3.4], [-21, 0]];
    const all = pts.concat(pts.slice(1, -1).reverse().map(([x, y]) => [x, -y]));
    const sk = (ctx, y0, y1) => { const g = ctx.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, '#f2c2c8'); g.addColorStop(1, '#d9929f'); return g; };
    return paintFur({
      box: [-27, -16, 32, 16], k: 16, path: smoothClosed(all), round: 9.2, seed: 29, ramp: RAMP, hairW: .1, density: 66, edge: .12,
      bumps: [[-12, -4.8, 5.4, 3.6, 1.1], [-12, 4.8, 5.4, 3.6, 1.1], [7, -4.6, 3.6, 2.8, 1], [7, 4.6, 3.6, 2.8, 1], [19, 0, 5, 3, 1], [12, -6.4, 1.6, 1.8, -.6], [12, 6.4, 1.6, 1.8, -.6], [-4, 0, 16, 1, -.42]],
      flow: (x, y) => [-1, y * .1], len: (x) => lerp(.42, 1.3, sstep(26, 12, x)),
      under: ctx => {
        [-1, 1].forEach(s => {
          ctx.fillStyle = sk(ctx, -14, 14);
          ctx.beginPath(); ctx.ellipse(12.5, s * 9.8, 2.2, 1.15, s * .65, 0, 7); ctx.fill();
          digit(ctx, 13.4, s * 10.5, 16.2, s * 12.4, .32); digit(ctx, 13.8, s * 10.1, 17.2, s * 11.3, .3); digit(ctx, 14, s * 9.6, 17.2, s * 9.9, .28);
          ctx.fillStyle = sk(ctx, -14, 14);
          ctx.beginPath(); ctx.ellipse(-8, s * 9.9, 3.2, 1.1, s * -.1, 0, 7); ctx.fill();
          digit(ctx, -5.4, s * 10.5, -2.6, s * 11.6, .3); digit(ctx, -5.1, s * 10.1, -1.9, s * 10.5, .3); digit(ctx, -5.3, s * 9.6, -2.3, s * 9.3, .26);
        });
      },
      over: ctx => {
        ctx.save(); ctx.globalCompositeOperation = 'source-atop'; pinkBlush(ctx, 26, 0, 3.4, .3); ctx.restore();
        [-1, 1].forEach(s => {
          // ear lying back, seen from above
          ctx.save(); ctx.translate(14.1, s * 5.9); ctx.rotate(s * .32);
          const e = ctx.createRadialGradient(0, 0, .2, 0, 0, 2.9); e.addColorStop(0, '#c98a97'); e.addColorStop(.6, '#e6b6bd'); e.addColorStop(1, '#efdcd6');
          ctx.fillStyle = e; ctx.beginPath(); ctx.ellipse(-.3, s * .5, 2.5, 1.85, 0, 0, 7); ctx.fill();
          ctx.strokeStyle = 'rgba(250,240,234,.85)'; ctx.lineWidth = .2; ctx.stroke(); ctx.restore();
          // eye: domed, dark ruby, in a shallow socket
          const ex = 21.4, ey = s * 3.05;
          ctx.fillStyle = 'rgba(140,110,104,.5)'; ctx.beginPath(); ctx.ellipse(ex, ey, 1.28, 1.02, 0, 0, 7); ctx.fill();
          const g = ctx.createRadialGradient(ex - .3, ey - .3, .05, ex, ey, 1); g.addColorStop(0, '#c23049'); g.addColorStop(.55, '#6a0d1e'); g.addColorStop(1, '#1c0307');
          ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(ex, ey, 1, .82, 0, 0, 7); ctx.fill();
          ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.beginPath(); ctx.ellipse(ex - .3, ey - .28, .24, .17, 0, 0, 7); ctx.fill();
        });
        const g = ctx.createRadialGradient(26.6, 0, .1, 26.9, 0, 1.5); g.addColorStop(0, '#f2bcc6'); g.addColorStop(1, '#c47a8b');
        ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(26.9, 0, 1.15, 1.1, 0, 0, 7); ctx.fill();
        ctx.fillStyle = '#6a2a39'; [-1, 1].forEach(s => { ctx.beginPath(); ctx.ellipse(27.3, s * .44, .17, .26, s * .5, 0, 7); ctx.fill(); });
      }
    });
  }

  // ------------------------------------------------------------- albino rabbit (front view, origin at head centre)
  const RB_HEAD = 'M0 -112 C50 -116 106 -96 128 -48 C144 -10 124 42 88 84 C62 112 32 132 0 134 C-32 132 -62 112 -88 84 C-124 42 -144 -10 -128 -48 C-106 -96 -50 -116 0 -112Z';
  const rbRamp = [[176, 160, 152], [232, 224, 217], [255, 254, 251]];
  function rbHead() {
    return paintFur({
      box: [-152, -130, 152, 150], k: 3, path: RB_HEAD, round: 92, seed: 43, ramp: rbRamp, hairW: .75, density: .42, edge: .5,
      light: [-.12, -.4, .91],
      bumps: [[-25, 84, 28, 24, 13], [25, 84, 28, 24, 13], [0, 22, 24, 62, 12], [-70, -20, 30, 24, 8], [70, -20, 30, 24, 8], [-96, 44, 32, 38, 5], [96, 44, 32, 38, 5], [0, 112, 26, 14, -7]],
      flow: (x, y) => { const dx = x, dy = y - 66, r = Math.hypot(dx, dy) || 1; return [dx / r + (y < 40 ? 0 : x * .002), dy / r]; },
      len: (x, y) => lerp(3.4, 14, sstep(6, 120, Math.hypot(x, y - 66))),
      order: (x, y) => -Math.hypot(x, y - 66),
      over: ctx => {
        ctx.save(); ctx.globalCompositeOperation = 'source-atop'; pinkBlush(ctx, 0, 72, 26, .34); ctx.restore();
        ctx.lineCap = 'round';
        ctx.strokeStyle = 'rgba(136,108,104,.85)'; ctx.lineWidth = 1.05;
        ctx.beginPath(); ctx.moveTo(0, 77.5); ctx.lineTo(0, 91); ctx.quadraticCurveTo(-11, 101, -25, 95); ctx.moveTo(0, 91); ctx.quadraticCurveTo(11, 101, 25, 95); ctx.stroke();
        ctx.fillStyle = 'rgba(146,118,112,.45)';
        [-1, 1].forEach(s => { for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { ctx.beginPath(); ctx.arc(s * (16 + i * 8.6 + j * 2), 78 + j * 7.4 - i * 1.2, .7, 0, 7); ctx.fill(); } });
      }
    });
  }
  function rbEar() {
    const T = -230, s = 1, path = `M${s * 42} -98 C${s * 26} ${T * .55} ${s * 34} ${T * .92} ${s * 62} ${T} C${s * 96} ${T * .92} ${s * 106} ${T * .55} ${s * 90} -82Z`;
    return paintFur({
      box: [20, -244, 112, -70], k: 5, path, round: 24, seed: 53, ramp: rbRamp, hairW: .5, density: 1.3, edge: .5, light: [-.2, -.5, .84],
      flow: () => [0, -1], len: () => 6,
      over: ctx => {
        const inner = new Path2D(`M54 -92 C44 ${T * .55} 46 ${T * .86} 62 ${T * .95} C84 ${T * .86} 92 ${T * .55} 80 -86Z`);
        ctx.save(); ctx.filter = 'blur(5px)';
        const g = ctx.createLinearGradient(0, T, 0, -82); g.addColorStop(0, '#ecc0c6'); g.addColorStop(.5, '#efbcc4'); g.addColorStop(1, '#c98794');
        ctx.fillStyle = g; ctx.fill(inner); ctx.restore();
        ctx.save(); ctx.clip(inner); ctx.lineCap = 'round';
        const r = rng(61), V = (x0, y0, x1, y1, x2, y2, w) => { ctx.lineWidth = w; ctx.strokeStyle = `rgba(178,78,98,${.3 + w * .1})`; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo(x1, y1, x2, y2); ctx.stroke(); };
        V(64, -88, 60, -130, 63, -212, 1.5);
        for (let i = 0; i < 12; i++) { const y = -105 - i * 8.8, sd = i % 2 ? 1 : -1; V(61.5 + r() * 1.5, y, 61 + sd * 9, y - 12, 62 + sd * (10 + r() * 10), y - 20 - r() * 8, .55); }
        const sh = ctx.createLinearGradient(0, -120, 0, -82); sh.addColorStop(0, 'rgba(120,58,74,0)'); sh.addColorStop(1, 'rgba(120,58,74,.5)');
        ctx.fillStyle = sh; ctx.fillRect(40, -130, 60, 50); ctx.restore();
        ctx.strokeStyle = 'rgba(255,250,246,.6)'; ctx.lineWidth = .35;
        for (let i = 0; i < 320; i++) { const x = 46 + r() * 44, y = -210 + r() * 120; if (ctx.isPointInPath(inner, (x - 20) * 5, (y + 244) * 5)) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + (r() - .5) * 2.4, y - 3 - r() * 4); ctx.stroke(); } }
      }
    });
  }
  function rbBody() {
    return paintFur({
      box: [-264, 84, 264, 256], k: 2, path: 'M-250 250 C-230 130 -130 96 0 96 C130 96 230 130 250 250Z', round: 120, seed: 59, ramp: rbRamp, hairW: .9, density: .42, edge: .5,
      light: [-.12, -.4, .91], flow: (x, y) => [x * .006, 1], len: () => 16
    });
  }

  // ------------------------------------------------------------- guinea pig, dorsal view with a depilated test field
  function guineaPig() {
    return paintFur({
      box: [112, 28, 906, 412], k: 1.25, path: 'M138 232 C128 118 236 50 400 50 C540 50 666 66 750 112 C806 142 846 176 880 214 C884 220 884 226 880 232 C846 268 806 300 750 330 C666 376 540 392 400 390 C236 388 148 342 138 232Z',
      round: 150, seed: 67, ramp: [[66, 42, 20], [138, 96, 52], [216, 170, 116]], hairW: 1.1, density: .3, edge: .22, light: [-.2, -.55, .8],
      bumps: [[230, 220, 100, 130, 12], [640, 220, 80, 100, 10], [810, 220, 60, 44, 14]],
      flow: (x, y) => [-1, (y - 220) * .0045], len: (x) => lerp(7, 19, sstep(880, 620, x)),
      under: ctx => {
        [[158, 128], [282, 312]].forEach(([a, b], i) => { const s = i ? -1 : 1, g = ctx.createLinearGradient(800, a, 850, b); g.addColorStop(0, '#b78a7e'); g.addColorStop(1, '#d6aea1'); ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(800, a); ctx.bezierCurveTo(808, b, 840, b - s * 4, 850, a - s * 8 + s * 0); ctx.bezierCurveTo(846, a + s * 12, 824, a + s * 20, 806, a + s * 18); ctx.fill(); });
      },
      over: ctx => {
        const patch = new Path2D(); patch.roundRect(296, 116, 408, 208, 74);
        ctx.save(); ctx.filter = 'blur(3.5px)'; const g = ctx.createRadialGradient(500, 210, 40, 500, 220, 250); g.addColorStop(0, '#f6dcc7'); g.addColorStop(.7, '#eec6a9'); g.addColorStop(1, '#e3b08f'); ctx.fillStyle = g; ctx.fill(patch); ctx.restore();
        ctx.save(); ctx.clip(patch);
        const r = rng(13);
        for (let i = 0; i < 2600; i++) { const x = 296 + r() * 408, y = 116 + r() * 208, a = (r() * .9) + 2.7; ctx.strokeStyle = `rgba(92,62,36,${.12 + r() * .32})`; ctx.lineWidth = .7; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * (1 + r() * 2), y + Math.sin(a) * (1 + r() * 2)); ctx.stroke(); }
        ctx.restore();
        [[826, 178], [826, 262]].forEach(([x, y]) => {
          ctx.fillStyle = 'rgba(30,16,8,.55)'; ctx.beginPath(); ctx.ellipse(x, y, 11.5, 10, 0, 0, 7); ctx.fill();
          const e = ctx.createRadialGradient(x - 2.5, y - 2.5, .5, x, y, 9); e.addColorStop(0, '#3b2416'); e.addColorStop(1, '#080503'); ctx.fillStyle = e; ctx.beginPath(); ctx.ellipse(x, y, 8.8, 7.8, 0, 0, 7); ctx.fill();
          ctx.fillStyle = 'rgba(255,255,255,.88)'; ctx.beginPath(); ctx.ellipse(x - 3, y - 3, 2, 1.5, 0, 0, 7); ctx.fill();
        });
        [214, 226].forEach(y => { ctx.fillStyle = '#6f4750'; ctx.beginPath(); ctx.ellipse(880, y, 3, 2.2, 0, 0, 7); ctx.fill(); });
      }
    });
  }

  // ------------------------------------------------------------- frog: moist skin, marbled dorsum, pale belly
  function tube(pts, w0, w1, belly = 0) {
    const n = pts.length - 1, L = [], R = [];
    pts.forEach((p, i) => { const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1, t = i / n, w = (lerp(w0, w1, t) + belly * Math.sin(Math.PI * t)) / 2; L.push([p[0] - dy / l * w, p[1] + dx / l * w]); R.push([p[0] + dy / l * w, p[1] - dx / l * w]); });
    return 'M' + L.concat(R.reverse()).map(p => `${f2(p[0])} ${f2(p[1])}`).join('L') + 'Z';
  }
  const quad = (a, c, b, n = 16) => Array.from({ length: n + 1 }, (_, i) => { const t = i / n, u = 1 - t; return [u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]; });
  const mix3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
  // domain-warped noise gives the irregular, hard-edged patches of real frog skin
  function warped(seed, f) { const a = noise2(seed), b = noise2(seed + 2), c = noise2(seed + 4); return (x, y) => a(x * f + (b(x * .05, y * .05) - .5) * 5, y * f + (c(x * .05, y * .05) - .5) * 5); }
  const segDist = (x, y, x0, y0, x1, y1) => { const vx = x1 - x0, vy = y1 - y0, t = clamp(((x - x0) * vx + (y - y0) * vy) / (vx * vx + vy * vy)); return Math.hypot(x - x0 - vx * t, y - y0 - vy * t); };
  const FLAT = [[30, 30, 20], [120, 120, 90], [220, 220, 190]];

  function frogBody() {
    const head = 'M500 94 C522 98 546 126 548 148 C548 160 530 170 500 170 C470 170 452 160 452 148 C454 126 478 98 500 94Z';
    const torso = 'M500 152 C538 152 556 176 554 212 C552 248 532 272 500 274 C468 272 448 248 446 212 C444 176 462 152 500 152Z';
    const arm = s => tube(quad([500 + s * 44, 176], [500 + s * 72, 205], [500 + s * 58, 238]), 16, 7.5, 3);
    const fingers = s => [-.5, -.16, .18, .52].map(a => tube([[500 + s * 58, 236], [500 + s * (58 + Math.sin(a) * 9), 246], [500 + s * (58 + Math.sin(a) * 17), 236 + Math.cos(a) * 22]], 3.2, 2.2));
    const paths = [head, torso, 'M454 144 L546 144 L556 200 L444 200Z', arm(-1), arm(1), ...fingers(-1), ...fingers(1)];
    const blot = warped(91, .085), fine = warped(103, .3), fleck = warped(111, .5), grain = noise2(115);
    const ridge = (x, y, s) => { if (y < 160 || y > 260) return 0; return Math.exp(-(((x - (500 + s * (21 + 15 * Math.sin(Math.PI * (y - 160) / 100)))) / 2.4) ** 2)); };
    const r = rng(97);
    return paintFur({
      box: [428, 84, 572, 286], k: 6, paths, round: 34, seed: 71, hair: false, ramp: FLAT, light: [-.3, -.65, .7], spec: .34, specP: 60, litMin: .4, litGain: .74,
      bumps: [[469, 131, 11, 11, 9], [531, 131, 11, 11, 9], [500, 248, 22, 18, 7], [467, 182, 13, 16, 3], [533, 182, 13, 16, 3], [500, 120, 7, 22, 3]],
      relief: (x, y) => (grain(x * .9, y * .9) - .5) * .42 + (grain(x * 2.2, y * 2.2) - .5) * .12 + (ridge(x, y, -1) + ridge(x, y, 1)) * .7,
      albedo: (x, y, s, edge) => {
        const front = sstep(232, 128, y), onArm = Math.abs(x - 500) > 46 && y > 178;
        let c = mix3([90, 96, 36], [136, 154, 46], front * .9 + .1);
        c = mix3(c, [176, 180, 64], clamp((fine(x, y) - .42) * 1.1 * front));
        // crisp dark marbling, denser towards the rear and flanks
        const dens = lerp(.57, .72, front) - clamp(Math.abs(x - 500) / 60) * .03;
        const b1 = sstep(dens, dens + .022, blot(x, y) * .78 + fine(x, y) * .22);
        c = mix3(c, [36, 30, 15], b1 * .94);
        const fl = sstep(.76, .8, fleck(x, y)) * (1 - front) * (1 - b1 * .5);
        c = mix3(c, [190, 186, 112], fl * .6);
        c = mix3(c, [194, 208, 96], (1 - sstep(1.2, 3.2, Math.abs(x - 500))) * sstep(112, 130, y) * sstep(268, 250, y) * .9);
        c = mix3(c, [176, 182, 96], clamp(ridge(x, y, -1) + ridge(x, y, 1)) * .32);
        // dark band from the eye back over the tympanum, cream upper lip
        for (const k of [-1, 1]) { const dd = segDist(x, y, 500 + k * 31, 130, 500 + k * 42, 156); c = mix3(c, [74, 48, 24], 1 - sstep(5, 8.5, dd)); }
        if (y < 168 && y > 100) c = mix3(c, [228, 222, 158], 1 - sstep(1, 3.2, edge));
        if (onArm) { const hand = sstep(226, 240, y); c = mix3(c, [212, 188, 160], hand * .92); c = mix3(c, [58, 44, 22], (1 - hand) * sstep(.55, .6, blot(x, y + 6)) * .7); }
        return c;
      },
      over: ctx => {
        ctx.save(); ctx.globalCompositeOperation = 'source-atop';
        for (let i = 0; i < 620; i++) { const x = 440 + r() * 120, y = 100 + r() * 175; ctx.fillStyle = r() < .55 ? 'rgba(26,28,10,.6)' : 'rgba(232,230,160,.5)'; ctx.globalAlpha = .2 + r() * .4; ctx.beginPath(); ctx.arc(x, y, .25 + r() * .5, 0, 7); ctx.fill(); }
        ctx.restore();
        [-1, 1].forEach(s => {
          const cx = 500 + s * 31, cy = 130;
          const ty = ctx.createRadialGradient(cx + s * 9, 150, .4, cx + s * 9, 151, 6.2); ty.addColorStop(0, '#94754a'); ty.addColorStop(.8, '#5a4122'); ty.addColorStop(1, '#2e2010'); ctx.fillStyle = ty; ctx.beginPath(); ctx.ellipse(cx + s * 9, 151, 6, 5.5, 0, 0, 7); ctx.fill();
          ctx.fillStyle = 'rgba(255,245,210,.5)'; ctx.beginPath(); ctx.ellipse(cx + s * 7.6, 149, 1.5, .9, 0, 0, 7); ctx.fill();
          ctx.fillStyle = '#2b2c10'; ctx.beginPath(); ctx.ellipse(cx, cy, 10.2, 9.5, 0, 0, 7); ctx.fill();
          const iris = ctx.createRadialGradient(cx - 2, cy - 3, .6, cx, cy, 7.6); iris.addColorStop(0, '#f3dc84'); iris.addColorStop(.55, '#c7972c'); iris.addColorStop(1, '#4d3808'); ctx.fillStyle = iris; ctx.beginPath(); ctx.ellipse(cx, cy - .6, 7.4, 6.9, 0, 0, 7); ctx.fill();
          ctx.strokeStyle = 'rgba(58,36,6,.5)'; ctx.lineWidth = .3; for (let a = 0; a < 6.28; a += .2) { ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * 3.6, cy - .6 + Math.sin(a) * 2.7); ctx.lineTo(cx + Math.cos(a + .08) * 7, cy - .6 + Math.sin(a + .08) * 6.4); ctx.stroke(); }
          ctx.fillStyle = '#080602'; ctx.beginPath(); ctx.ellipse(cx, cy - .6, 5, 2.7, 0, 0, 7); ctx.fill();
          ctx.fillStyle = 'rgba(255,255,255,.95)'; ctx.beginPath(); ctx.ellipse(cx - 2.3, cy - 3.3, 1.5, 1, -.3, 0, 7); ctx.fill();
          ctx.strokeStyle = 'rgba(30,36,10,.7)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.ellipse(cx, cy, 8.6, 8, 0, 3.5, 5.9); ctx.stroke();
        });
        ctx.fillStyle = '#141a06'; [494, 506].forEach(x => { ctx.beginPath(); ctx.ellipse(x, 106, 1.25, .95, 0, 0, 7); ctx.fill(); });
      }
    });
  }

  // belly-up frog pinned on a board. L: {box,k,round,paths,creases,pale(x,y),seed}
  function frogVentral(L) {
    const blot = warped(L.seed + 3, .11), wr = noise2(L.seed + 7), wr2 = noise2(L.seed + 9), sp = warped(L.seed + 13, .05);
    return paintFur({
      box: L.box, k: L.k, paths: L.paths, round: L.round, seed: L.seed, hair: false, ramp: FLAT, light: [-.18, -.5, .85], spec: .22, specP: 34, litMin: .46, litGain: .68,
      bumps: L.bumps || [],
      relief: (x, y) => (wr(x * .07, y * .2) - .5) * .9 + (wr2(x * .5, y * .5) - .5) * .12,
      albedo: (x, y, s, edge) => {
        let c = mix3([238, 229, 200], [248, 241, 220], sp(y, x));
        c = mix3(c, [196, 186, 160], sstep(.5, .85, sp(x, y)) * .32);          // faint grey mottling of the belly
        const rim = Math.pow(1 - sstep(.5, (L.rim || 12) * 1.5, edge), 1.6);
        if (rim > 0) {
          let d = mix3([150, 158, 54], [186, 180, 76], wr2(x * .1, y * .1));
          d = mix3(d, [88, 84, 40], sstep(.56, .7, blot(x, y)) * .6);
          c = mix3(c, d, rim);
        }
        if (L.pale(x, y)) c = mix3(c, [188, 160, 142], .86);
        return c;
      },
      over: ctx => {
        ctx.save(); ctx.globalCompositeOperation = 'source-atop'; ctx.filter = `blur(${L.k * 1.1}px)`; ctx.strokeStyle = 'rgba(70,58,30,.3)'; ctx.lineWidth = 3;
        L.creases.forEach(p => ctx.stroke(new Path2D(p))); ctx.restore();
        ctx.save(); ctx.globalCompositeOperation = 'source-atop'; ctx.strokeStyle = 'rgba(112,96,60,.5)'; ctx.lineWidth = .8; (L.folds || []).forEach(p => ctx.stroke(new Path2D(p))); ctx.restore();
      }
    });
  }
  function toesAt(x, y, ang, len, w) {
    const a = [-.48, -.22, 0, .24, .5], l = [.6, .82, 1, 1.2, .84];
    const toes = a.map((d, i) => [x + Math.cos(ang + d) * len * l[i], y + Math.sin(ang + d) * len * l[i]]);
    return [`M${x} ${y}L${toes.map(t => f2(lerp(x, t[0], .72)) + ' ' + f2(lerp(y, t[1], .72))).join('L')}Z`, ...toes.map(t => tube([[x, y], [(x + t[0]) / 2, (y + t[1]) / 2], t], w, w * .62))];
  }
  function ventral07() {
    const M = (p, s) => s > 0 ? p : p.map(q => [660 - q[0], q[1]]), paths = [], creases = [];
    [1, -1].forEach(s => {
      const thigh = M(quad([300, 346], [222, 324], [150, 352]), s), shank = M(quad([150, 352], [198, 412], [272, 404]), s), foot = M(quad([272, 404], [212, 416], [152, 386], 8), s);
      const arm = M(quad([268, 208], [214, 232], [196, 200]), s), hand = M(quad([196, 200], [178, 184], [160, 174], 6), s);
      const end = foot[foot.length - 1], dirF = Math.atan2(386 - 412, s > 0 ? -60 : 60), hEnd = hand[hand.length - 1], dirH = s > 0 ? Math.PI * 1.12 : -Math.PI * .12;
      const T = tube(thigh, 64, 30, 8), S = tube(shank, 28, 14, 5);
      paths.push(S, tube(foot, 15, 8), T, tube(arm, 36, 20, 6), tube(hand, 20, 11), ...toesAt(end[0], end[1], dirF, 30, 5), ...toesAt(hEnd[0], hEnd[1], dirH, 22, 4.2));
    });
    const flank = 'M262 176 C232 198 218 250 228 306 C238 350 280 374 330 378 C380 374 422 350 432 306 C442 250 428 198 398 176 C368 158 292 158 262 176Z';
    const head = 'M330 40 C372 40 412 78 418 122 C420 148 410 164 396 172 C360 180 300 180 264 172 C250 164 240 148 242 122 C248 78 288 40 330 40Z';
    paths.push(flank, head); creases.push(flank, head);
    return frogVentral({
      box: [96, 28, 564, 448], k: 2.2, round: 62, seed: 131, paths, creases, rim: 9,
      folds: ['M288 180 Q330 192 372 180', 'M292 188 Q330 200 368 188', 'M280 150 Q330 166 380 150'],
      pale: (x, y) => { const X = Math.min(x, 660 - x); return (y > 392 && X > 150) || (X < 176 && y < 215); }
    });
  }
  function ventral12() {
    const M = (p, s) => s > 0 ? p : p.map(q => [1000 - q[0], q[1]]), paths = [], creases = [];
    [1, -1].forEach(s => {
      const thigh = M(quad([458, 372], [424, 434], [398, 500]), s), arm = M(quad([440, 188], [400, 208], [368, 246]), s);
      const T = tube(thigh, 56, 26, 8), A = tube(arm, 30, 16, 4);
      const toe = s > 0 ? Math.PI * .46 : Math.PI * .54, fing = s > 0 ? Math.PI * .86 : Math.PI * .14, e = M([[398, 500]], s)[0], h = M([[366, 250]], s)[0];
      paths.push(T, A, ...toesAt(e[0], e[1], toe, 46, 7), ...toesAt(h[0], h[1], fing, 25, 4.6));
    });
    const body = 'M500 62 C540 62 566 88 570 120 C574 150 590 170 596 200 C606 250 604 320 584 360 C570 385 540 398 500 398 C460 398 430 385 416 360 C396 320 394 250 404 200 C410 170 426 150 430 120 C434 88 460 62 500 62 Z';
    paths.push(body); creases.push(body);
    return frogVentral({
      box: [330, 48, 670, 566], k: 2.4, round: 74, seed: 149, paths, creases, rim: 13,
      folds: ['M470 120 Q500 135 530 120', 'M478 138 Q500 143 522 138', 'M470 146 Q500 151 530 146', 'M462 154 Q500 159 538 154'],
      pale: (x, y) => { const X = Math.min(x, 1000 - x); return y > 500 || (X < 372 && y > 232); }
    });
  }

  global.ANI_JOBS = {
    'side-rat': () => sideBody('rat'), 'side-mouse': () => sideBody('mouse'), earS: earSide,
    footH: () => feet('hind', false), footF: () => feet('fore', false), footHfar: () => feet('hind', true), footFfar: () => feet('fore', true),
    top: topBody, rbHead, rbEar, rbBody, guineaPig, frogBody, frogVen07: ventral07, frogVen12: ventral12
  };

})(window);
