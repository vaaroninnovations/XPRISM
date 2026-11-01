/* XPRISM: uniform viva-voce feedback across all experiments.
   Shows the score and per-question feedback inside the viva window (instead of a status-bar message
   that is hidden while the student is on the Observation tab). */
(function () {
  function modal() { return document.getElementById('modalQuestions'); }
  function banner(text, ok) {
    const m = modal(); if (!m) return;
    let s = m.querySelector('#quizScore');
    if (!s) {
      s = document.createElement('div'); s.id = 'quizScore';
      const body = m.querySelector('#quizBody') || m.querySelector('.overflow-y-auto');
      if (body && body.parentNode) body.parentNode.insertBefore(s, body);
      else { const card = m.firstElementChild; card.insertBefore(s, card.children[1] || null); }
    }
    s.className = 'p-2.5 rounded-lg text-xs font-semibold ' + (ok ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-amber-50 text-amber-800 border border-amber-200');
    s.textContent = text;
  }
  function group(name) {
    const ins = Array.from(document.querySelectorAll('input[type=radio][name="' + name + '"]'));
    if (!ins.length) return null;
    let w = ins[0].parentElement;
    while (w && !ins.every(i => w.contains(i))) w = w.parentElement;
    return { w, ins };
  }
  function mark(name, correct, chosen, explain) {
    const g = group(name); if (!g) return;
    const ok = String(chosen) === String(correct);
    let fb = Array.from(g.w.children).find(c => c.classList && c.classList.contains('mcp-viva-fb'));
    if (!fb) { fb = document.createElement('p'); g.w.appendChild(fb); }
    const lab = g.ins.find(i => String(i.value) === String(correct));
    const txt = lab ? (lab.closest('label') || lab.parentElement).innerText.trim() : '';
    fb.className = 'mcp-viva-fb text-[11px] p-2 rounded mt-1 ' + (ok ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-rose-50 text-rose-800 border border-rose-200');
    fb.innerHTML = (ok ? '✓ Correct. ' : '✗ Correct answer: <b>' + txt + '</b>. ') + (explain || '');
  }
  function sound(ok) { try { if (typeof beep === 'function') beep(ok ? 'done' : 'warn'); } catch (e) { } }
  function score(sc, total) {
    const ok = sc / total >= 0.6;
    banner('Viva score: ' + sc + '/' + total + ' (' + Math.round(sc / total * 100) + '%)', ok);
    sound(ok);
    const b = modal() && (modal().querySelector('#quizBody') || modal().querySelector('.overflow-y-auto')); if (b) b.scrollTop = 0;
  }
  // used by pages with hard-coded answer keys
  window.mcpVivaResult = function (sc, total, key) {
    window.MCP_VIVA_LAST = { score: sc, total: total };
    if (window.MCP_EXAM) { banner('Exam mode: your answers are saved and will be marked when you submit the attempt.', true); return; }
    Object.keys(key || {}).forEach(n => { const c = document.querySelector('input[name="' + n + '"]:checked'); mark(n, key[n], c ? c.value : undefined); });
    score(sc, total);
  };
  // pages with a QUIZ array but no in-window feedback
  let hasQuiz = false; try { hasQuiz = typeof QUIZ !== 'undefined' && Array.isArray(QUIZ); } catch (e) { }
  if (hasQuiz && document.getElementById('quizBody') && !document.getElementById('quizScore')) {
    window.evaluateQuestions = function () {
      const ans = QUIZ.map((_, i) => { const c = document.querySelector('input[name="q' + i + '"]:checked'); return c ? c.value : undefined; });
      if (ans.some(a => a === undefined)) { banner('Please answer all ' + QUIZ.length + ' questions before submitting.', false); sound(false); return; }
      let sc = 0;
      QUIZ.forEach((q, i) => { if (+ans[i] === q.a) sc++; mark('q' + i, q.a, ans[i], q.e); });
      score(sc, QUIZ.length);
    };
  }
})();
