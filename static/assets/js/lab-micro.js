/* XPRISM organ-bath micro-animations.
   Small signs of life around the bath that the modules do not simulate themselves: glassy bubbles that pop into ripples,
   a moving water surface, air glugging into the reservoir as it empties, drops and ripples in the waste beaker,
   warm water rising in the jacket, a breathing heat lamp and a trembling air-pump needle.
   A module calls LabMicro.tick() once per frame and names the elements it already draws; anything it does not name,
   or that is missing from its scene, is skipped. Nothing here changes a reading or a result.
   With "reduce motion" switched on, bubbles keep their look and everything else stays still. */
const LabMicro = (() => {
  const STILL = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const NS = 'http://www.w3.org/2000/svg';
  const f = v => v.toFixed(1);
  let t = 0, pops = [], rings = [], glug = [], glugIn = 0, drops = [], dropIn = 0, tail = 0, streaks = null;

  // One bubble: thin bright wall, faint body, a highlight on the upper left
  function bubble(x, y, r) {
    return `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="#e0f2fe" fill-opacity=".22" stroke="#fff" stroke-opacity=".85" stroke-width="${f(Math.max(0.5, r * 0.26))}"/><circle cx="${f(x - r * 0.34)}" cy="${f(y - r * 0.36)}" r="${f(Math.max(0.35, r * 0.24))}" fill="#fff" opacity=".9"/>`;
  }

  // A bubble reached the surface at (x, y)
  function pop(x, y) { if (!STILL && pops.length < 10) pops.push({ x, y, a: 0 }); }

  // A <g> placed straight after an element the module draws, so it shares that element's clipping and stacking
  function layer(id, anchor, clip) {
    let g = document.getElementById(id);
    if (g && g.previousElementSibling === anchor) return g;
    if (g) g.remove();
    g = document.createElementNS(NS, 'g');
    g.id = id; g.setAttribute('pointer-events', 'none');
    if (clip) g.setAttribute('clip-path', clip);
    anchor.parentNode.insertBefore(g, anchor.nextSibling);
    return g;
  }
  const box = e => ({ x: +e.getAttribute('x'), y: +e.getAttribute('y'), w: +e.getAttribute('width'), h: +e.getAttribute('height') });

  function surface(o, dt) {
    const a = document.getElementById(o.after);
    if (!a) return;
    const g = layer('fxSurface', a);
    let s = '';
    if (o.wet) {
      const air = o.air || 0, amp = air ? 0.5 + Math.min(air, 5) * 0.22 : 0.18, n = 6, w = (o.x1 - o.x0 - 8) / n;
      let d = `M${f(o.x0 + 4)} ${f(o.y)}`;
      for (let i = 0; i < n; i++) d += `q${f(w / 2)} ${f(Math.sin(t * (air ? 5 : 1.6) + i * 1.7) * amp * 2)} ${f(w)} 0`;
      s += `<path d="${d}" fill="none" stroke="#fff" stroke-width="1" stroke-linecap="round" opacity="${air ? 0.55 : 0.3}"/>`;
    }
    pops = pops.filter(p => (p.a += dt / 0.55) < 1);
    pops.forEach(p => { s += `<ellipse cx="${f(p.x)}" cy="${f(p.y)}" rx="${f(2 + p.a * 8)}" ry="${f(0.7 + p.a * 2)}" fill="none" stroke="#fff" stroke-width="${f(1.1 - p.a * 0.7)}" opacity="${f((1 - p.a) * 0.8)}"/>`; });
    g.innerHTML = s;
  }

  // As the reservoir runs into the bath, air bubbles climb through what is left
  function reservoir(o, dt) {
    const e = document.getElementById(o.id);
    if (!e) return;
    const b = box(e), g = layer('fxReservoir', e);
    if (o.on && b.h > 10) { glugIn -= dt; if (glugIn <= 0) { glugIn = 0.35 + Math.random() * 0.45; glug.push({ x: b.x + b.w * (0.3 + Math.random() * 0.12), y: b.y + b.h - 3, r: 1.6 + Math.random() * 2, ph: Math.random() * 6 }); } }
    glug = glug.filter(p => (p.y -= (34 + p.r * 9) * dt) > b.y + 2);
    g.innerHTML = glug.map(p => bubble(p.x + Math.sin(p.y / 8 + p.ph) * 2.2, p.y, p.r)).join('') +
      (o.on && b.h > 2 ? `<path d="M${f(b.x + 6)} ${f(b.y)}q${f(b.w / 4)} ${f(Math.sin(t * 3) * 1.2)} ${f(b.w / 2 - 6)} 0t${f(b.w / 2 - 6)} 0" fill="none" stroke="#fff" stroke-width="1" opacity=".4"/>` : '');
  }

  // Ripples in the waste beaker while the bath drains (the module draws the stream), then a few slowing drops once the tap closes
  function waste(o, dt) {
    const e = document.getElementById(o.id);
    if (!e) return;
    const b = box(e), g = layer('fxWaste', e), cx = b.x + b.w / 2, top = b.y - 30;
    tail = o.on ? 2.2 : Math.max(0, tail - dt);
    if (tail > 0) {
      dropIn -= dt;
      if (dropIn <= 0) {
        if (o.on) { dropIn = 0.22; if (b.h > 1 && rings.length < 6) rings.push(0); }
        else { dropIn = 0.45 + (2.2 - tail) * 0.3; drops.push({ y: top, v: 30 }); }
      }
    }
    let s = '';
    drops = drops.filter(p => { p.v += 420 * dt; p.y += p.v * dt; if (p.y < b.y) return true; if (b.h > 1 && rings.length < 6) rings.push(0); return false; });
    drops.forEach(p => { s += `<path d="M${f(cx)} ${f(p.y - 4)}q2.200 3.200 0 5.200q-2.200 -2 0 -5.200z" fill="#bae6fd" opacity=".85"/>`; });
    rings = rings.map(a => a + dt / 0.5).filter(a => a < 1);
    rings.forEach(a => { s += `<ellipse cx="${f(cx)}" cy="${f(b.y + 0.5)}" rx="${f(2 + a * Math.min(14, b.w / 2 - 4))}" ry="${f(0.6 + a * 1.2)}" fill="none" stroke="#fff" stroke-width=".8" opacity="${f((1 - a) * 0.7)}"/>`; });
    g.innerHTML = s;
  }

  // Warm water from the circulator rising in the two visible sides of the jacket
  function jacket(o, dt) {
    const e = document.getElementById(o.id);
    if (!e) return;
    const b = box(e), g = layer('fxJacket', e, e.getAttribute('clip-path'));
    if (!o.on || b.h < 20) { g.innerHTML = ''; return; }
    if (!streaks) streaks = Array.from({ length: 8 }, (_, i) => ({ side: i % 2, u: Math.random(), k: 0.25 + Math.random() * 0.5, ph: Math.random() * 6 }));
    const band = Math.min(16, b.w * 0.11);
    g.innerHTML = streaks.map(p => {
      p.u = (p.u + dt * (0.1 + p.k * 0.08)) % 1;
      const x = (p.side ? b.x + b.w - band - 2 : b.x + 4) + p.k * (band - 4), y = b.y + b.h - 8 - p.u * (b.h - 22), sw = Math.sin(t * 2 + p.ph) * 2;
      return `<path d="M${f(x)} ${f(y)}q${f(sw)} -5 0 -10t0 -10" fill="none" stroke="#e0f2fe" stroke-width="1.3" stroke-linecap="round" opacity="${f(Math.sin(p.u * Math.PI) * 0.42)}"/>`;
    }).join('');
  }

  // The heat lamp breathes while the circulator is still warming up
  function lamp(o) {
    const e = document.getElementById(o.id);
    if (!e) return;
    const g = layer('fxLamp', e);
    g.innerHTML = o.on ? `<circle cx="${e.getAttribute('cx')}" cy="${e.getAttribute('cy')}" r="${f(+e.getAttribute('r') + 2.5 + Math.sin(t * 4) * 1.5)}" fill="${e.getAttribute('fill')}" opacity="${f(0.22 + Math.sin(t * 4) * 0.1)}"/>` : '';
  }

  // The pump's needle trembles with the diaphragm (call after the module has set the needle)
  function needle(o) {
    const e = document.getElementById(o.id);
    if (!e || !o.rate) return;
    const j = Math.sin(t * 46) * 0.3 + Math.sin(t * 29) * 0.2;
    e.setAttribute('x2', f(+e.getAttribute('x2') + j)); e.setAttribute('y2', f(+e.getAttribute('y2') - j * 0.6));
  }

  /* o = { surface: { after, x0, x1, y, wet, air }, reservoir: { id, on }, waste: { id, on }, jacket: { id, on },
           lamp: { id, on }, needle: { id, rate } }: every part is optional */
  function tick(dt, o) {
    if (STILL || !(dt > 0)) return;
    dt = Math.min(dt, 0.1); t += dt;
    if (o.waste) waste(o.waste, dt);
    if (o.surface) surface(o.surface, dt);
    if (o.reservoir) reservoir(o.reservoir, dt);
    if (o.jacket) jacket(o.jacket, dt);
    if (o.lamp) lamp(o.lamp);
    if (o.needle) needle(o.needle);
  }
  // true while a circulator is on and still below its set temperature, whatever the module calls the reading
  const warming = h => !!(h && h.on && (h.T != null ? h.T : h.Tj) < h.set - 0.2);
  return { bubble, pop, tick, warming };
})();
