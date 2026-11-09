// Injected into each module page. Every recipe leaves the module's main apparatus in use.
(function () {
  const load = () => { for (const n of ['loadReferenceDataset', 'runAllInstant']) if (typeof window[n] === 'function') { window[n](); return; } };

  // Place a dosed animal, press START and let the module's own simulation run.
  function trial(st, placeAct, secs, before, until) {
    load(); goStation(st);
    if (before) before();
    const m = S.mice.find(x => x.inj && x.inj.length >= (CFG.nInj || 1)) || S.mice[0];
    S.hand = m.uid; m.run = null;
    act(placeAct);
    act('start');
    for (let t = 0; t < secs; t += 0.1) { CFG.tick(0.1, 0.1); if (until && until(S.trial)) break; }
    if (typeof drawDyn === 'function') drawDyn();
    if (typeof anim4 === 'function') anim4();
  }

  // Organ bath with the tissue mounted and the reference responses written on the drum.
  function drum(pick) {
    load(); goStation(3);
    Object.assign(S.mount, { held: false, hook: true, lowered: true, lever: true, load: 1, level: 0, contact: 1, at: 0 });
    S.bath.L = 20; S.res.vol = 2000; S.air = 6;
    if (S.frog) S.frog.inDish = false;
    if (S.heat) { S.heat.on = true; S.heat.T = S.heat.set; if ('Tj' in S.heat) S.heat.Tj = S.heat.set; }
    if ('T' in S.bath) S.bath.T = S.heat.set;
    Object.assign(S.kymo, { paper: true, glazed: true, speed: 'slow', run: false });
    let x = 0; const tr = [[0, 0]], mk = [];
    pick(S.recs).forEach(r => {
      x += 2.5; tr.push([x, 0]); mk.push({ x, n: r.n });
      tr.push([x + .7, r.peak * .86], [x + 1.5, r.peak], [x + 3, r.peak * .96], [x + 3.4, r.peak * .2], [x + 4.2, 0]);
      x += 4.2;
    });
    x += 1; tr.push([x, 0]);
    S.trace = tr; S.marks = mk; S.kymo.x = x;
  }

  const R = {
    '01': () => { selectAnimal(0); },
    '03': () => { load(); goStation(4); const m = S.mice[0]; m.test = null; S.hand = m.uid; act('arena'); act('clips'); },
    '04': () => { load(); goStation(3); for (let i = 0; i < 6; i++) { const x = S.mice[i]; x.loc = 'hand'; S.hand = x.id; act3('lane', i); } act3('start'); },
    '05': () => { load(); goStation(4); S.box.fill(null); for (let i = 0; i < 12; i++) { const m = S.mice[i]; if (!m || !m.ptz) continue; m.test.ch = null; S.hand = m.uid; act('ch', i); } },
    '07': () => { load(); goStation(2); },
    '09': () => { load(); goStation(3); const x = S.mice[0]; x.loc = 'hand'; S.hand = x.id; act3('arena'); act3('astart'); },
    '10': () => { load(); goStation(4); const m = S.mice[0]; S.trial = { kind: 'cat', uid: m.uid, state: 'placed', k: 0, off: 0, flags: [], ang: THETA * 180 / Math.PI, hx: HX0, L: 0 }; m.loc = 'app'; drawDyn(); anim4(); },
    '11': () => trial(4, 'maze', 25),
    '12': () => drum(r => r.filter(x => x.series === 'none').slice(0, 7)),
    '14': () => drum(r => r.slice(-8)),
    '15': () => drum(r => r.slice(-8)),
    '16': () => drum(r => r.slice(-8)),
    '17': () => drum(r => r.slice(-8)),
    '19': () => { load(); goStation(3); S.hand = 0; act3('cyl'); },
    '20': () => { load(); goStation(3); S.hand = 0; act3('rest'); },
    '21': () => { load(); goStation(3); const r = S.rats[0]; r.reads[0] = null; startMeasure(r); },
    '24': () => { load(); goStation(4); const m = S.mice[0]; m.gut = { cutA: 'pylorus', cutB: 'ileo', laid: false }; layGut(m, 1); drawDyn(); },
    '25': () => { load(); goStation(3); },
    '26': () => { load(); goStation(6); },
    '27': () => { load(); goStation(6); },
    '28': () => trial(4, 'place', 40),
    '29': () => trial(4, 'place', 60, () => { S.bait = baitOf(S.mice[0]).slice(); }),
    '30': () => trial(4, 'place', 30),
    '31': () => trial(4, 'place', 25),
    '32': () => trial(4, 'place', 30),
    '33': () => trial(4, 'place', 400, null, T => T.M.on),
    '34': () => trial(4, 'place', 30),
  };
  window.__shot = n => { try { (R[n] || load)(); return 'ok'; } catch (e) { return 'ERR ' + e.message; } };
})();
