/* XPRISM: bridge between an experiment page and the lab server.
   Shows the mode (demo / practice / assignment / staff preview), runs the exam timer,
   locks shortcut controls in exam mode, and packages the student's results for submission. */
(function () {
  'use strict';
  var node = document.getElementById('mcp-ctx');
  if (!node) return;
  var C = {};
  try { C = JSON.parse(node.textContent); } catch (e) { return; }
  var submitted = false, busy = false, startedAt = Date.now();

  function h(tag, attrs, html) { var e = document.createElement(tag); for (var k in (attrs || {})) e.setAttribute(k, attrs[k]); if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function txt(el) { return el ? (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  function notify(msg, alert) { try { if (typeof showFeedback === 'function') { showFeedback(msg, !!alert); return; } } catch (e) { } try { if (typeof showConsoleMessage === 'function') { showConsoleMessage(msg, !!alert); return; } } catch (e) { } }

  // ------------------------------------------------------------ status bar in the sub-header
  var bar = h('div', { id: 'mcpBar', class: 'flex flex-wrap items-center gap-2 text-xs', role: 'status' });
  var sub = document.querySelector('.site-subheader');
  if (sub) { var tabs = sub.querySelector('[role=tablist]') || sub.lastElementChild; sub.insertBefore(bar, tabs); }
  else { bar.className += ' fixed bottom-3 left-3 z-50 bg-slate-900 text-white px-3 py-2 rounded-lg shadow-xl'; document.body.appendChild(bar); }

  var pill = function (cls, html) { return '<span class="px-2 py-0.5 rounded-md font-semibold ' + cls + '">' + html + '</span>'; };
  var link = function (href, label, cls) { return '<a href="' + esc(href) + '" class="px-2.5 py-1 rounded-md font-semibold ' + (cls || 'bg-slate-700 hover:bg-slate-600 text-white') + '">' + label + '</a>'; };

  if (C.mode === 'demo') {
    bar.innerHTML = pill('bg-amber-400 text-slate-900', 'DEMO') + '<span class="text-slate-300">Nothing is saved.</span>' + link(C.login, 'Sign in to save work', 'bg-teal-500 hover:bg-teal-400 text-white');
  } else if (C.mode === 'trial') {
    bar.innerHTML = pill('bg-amber-400 text-slate-900', 'FREE TRIAL') +
      '<span class="text-amber-100">One visit per module: leaving this page ends it.</span><span id="mcpTrialLeft" class="mono text-amber-300"></span>' +
      link('/modules/', 'Finish & back to lab');
    // confirm before any link that leaves this module (header, ‹ › arrows, footer)
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[href]');
      if (!a || a.target === '_blank') return;
      var href = a.getAttribute('href');
      if (!href || href.charAt(0) === '#' || href.indexOf('mailto:') === 0) return;
      if (!window.confirm('Leaving ends your free-trial visit to this module. After this it will be available by subscription only.\n\nLeave now?')) { e.preventDefault(); e.stopPropagation(); }
    }, true);
    var vEnd = new Date(C.visitStarted).getTime() + C.maxHours * 3600 * 1000;
    var tl = function () { var m = Math.max(0, Math.round((vEnd - Date.now()) / 60000)); var el = document.getElementById('mcpTrialLeft'); if (el) el.textContent = '(' + Math.floor(m / 60) + 'h ' + String(m % 60).padStart(2, '0') + 'm left)'; if (m > 0) setTimeout(tl, 30000); };
    tl();
  } else if (C.mode === 'practice') {
    bar.innerHTML = pill('bg-slate-600 text-white', 'PRACTICE') + '<span class="text-slate-300">Not submitted to faculty.</span>' + link(C.home, 'My assignments');
  } else if (C.mode === 'preview') {
    bar.innerHTML = pill('bg-indigo-500 text-white', 'STAFF PREVIEW') + (C.examMode ? pill('bg-rose-500 text-white', 'EXAM-MODE VIEW') : '') + link(C.home, 'Dashboard');
  } else if (C.mode === 'closed') {
    bar.innerHTML = pill('bg-rose-500 text-white', 'NOT SUBMITTABLE') + '<span class="text-rose-200 max-w-md">' + esc(C.reason) + '</span>' + link(C.home, 'My assignments');
  } else if (C.mode === 'assignment') {
    bar.innerHTML = pill('bg-teal-500 text-white', 'ASSIGNMENT') +
      '<span class="text-slate-300">Attempt ' + C.attemptNo + '/' + C.maxAttempts + (C.overdue ? ' • <b class="text-rose-300">late</b>' : '') + '</span>' +
      (C.examMode ? pill('bg-rose-500 text-white', 'EXAM') + '<span id="mcpTimer" class="seg text-base text-amber-300 px-1" aria-live="polite">--:--</span>' : '') +
      '<button id="mcpSubmit" class="px-3 py-1 rounded-md bg-emerald-500 hover:bg-emerald-400 text-white font-bold shadow">Submit to faculty</button>';
    document.getElementById('mcpSubmit').addEventListener('click', function () { openConfirm(false); });
    window.addEventListener('beforeunload', function (e) { if (!submitted) { e.preventDefault(); e.returnValue = ''; } });
  }
  // this module's entry in the user guide; a new tab, so it never ends a trial visit or an attempt
  if (!C.examMode && C.expNo) bar.insertAdjacentHTML('beforeend', '<a href="/documentation/#exp-' + String(C.expNo).padStart(2, '0') + '" target="_blank" class="px-2.5 py-1 rounded-md font-semibold bg-slate-700 hover:bg-slate-600 text-white">Guide ↗</a>');

  // ------------------------------------------------------------ exam mode lockdown
  var BLOCK = ['doseAllInstant', 'loadReferenceDataset', 'autoFillCurrentState', 'fillAllMockData', 'skipAbsorption', 'autoRunTrial', 'runFullProtocol',
    'instantRunGroup', 'skipWait', 'runAllInstant', 'runCompleteBatchExperiment', 'fillSampleVideoDataset', 'instantTimePoint', 'runSeries', 'runAll',
    'guidedRun', 'runStandards', 'pilotRun', 'processAll', 'measureAll', 'runPlanInstant',
    'verifyNumber', 'verifyUnknownDeduction', 'submitEvaluation'];          // answer checkers would reveal the true value
  var HIDE_ONLY = ['openResultsModal'];                                     // the summary may name the unknown; the bridge still uses it internally
  var LABEL_RX = /assistant (tests|classifies)|auto-time/i;
  function lockdown() {
    window.MCP_EXAM = true;
    // viva: answers are recorded but not marked until the attempt is submitted
    var hasQuiz = false; try { hasQuiz = typeof QUIZ !== 'undefined' && Array.isArray(QUIZ); } catch (e) { }
    if (hasQuiz) {
      window.evaluateQuestions = function () {
        var m = document.getElementById('modalQuestions'); if (!m) return;
        var s = m.querySelector('#quizScore');
        if (!s) { s = document.createElement('div'); s.id = 'quizScore'; var body = m.querySelector('#quizBody'); body.parentNode.insertBefore(s, body); }
        s.className = 'p-2.5 rounded-lg text-xs font-semibold bg-sky-50 text-sky-800 border border-sky-200';
        s.textContent = 'Exam mode: your answers are saved and will be marked when you submit the attempt.';
        m.querySelectorAll('[id^=qexp], .mcp-viva-fb').forEach(function (e) { e.classList.add('hidden'); });
      };
    }
    var css = document.createElement('style');
    css.textContent = '#vivaScoreDisplay, #unknownVerdictBox, #deductionOut, #answerOut { visibility: hidden !important; }';
    document.head.appendChild(css);
    BLOCK.forEach(function (n) { if (typeof window[n] === 'function' && !window[n].__mcpBlocked) { var f = function () { notify('This shortcut is switched off in exam mode.', true); }; f.__mcpBlocked = true; try { window[n] = f; } catch (e) { } } });
    var sweep = function () {
      document.querySelectorAll('[onclick]').forEach(function (el) {
        if (el.dataset.mcpLocked) return;
        var oc = (el.getAttribute('onclick') || '').trim();
        if (BLOCK.concat(HIDE_ONLY).some(function (n) { return oc.indexOf(n + '(') === 0 || oc.indexOf(';' + n + '(') >= 0; })) { el.style.display = 'none'; el.dataset.mcpLocked = '1'; }
      });
      document.querySelectorAll('label').forEach(function (l) {
        if (l.dataset.mcpLocked || !LABEL_RX.test(l.textContent || '')) return;
        var cb = l.querySelector('input[type=checkbox]'); if (cb) cb.checked = false;
        l.style.display = 'none'; l.dataset.mcpLocked = '1';
      });
    };
    sweep();
    var pending = false;
    new MutationObserver(function () { if (pending) return; pending = true; setTimeout(function () { pending = false; sweep(); }, 250); }).observe(document.body, { childList: true, subtree: true });
  }
  if (C.examMode && (C.mode === 'assignment' || C.mode === 'preview')) lockdown();

  // ------------------------------------------------------------ exam timer
  if (C.mode === 'assignment' && C.examMode && C.deadline) {
    var deadline = new Date(C.deadline).getTime(), warned = false;
    var tick = function () {
      var left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      var el = document.getElementById('mcpTimer');
      if (el) { el.textContent = String(Math.floor(left / 60)).padStart(2, '0') + ':' + String(left % 60).padStart(2, '0'); el.className = 'seg text-base px-1 ' + (left < 300 ? 'text-rose-300' : 'text-amber-300'); }
      if (!warned && left <= 300 && left > 0) { warned = true; notify('5 minutes left. Your work will be submitted automatically when time is up.', true); }
      if (left <= 0 && !submitted && !busy) { notify('Time is up: submitting your work now.', true); doSubmit(true); return; }
      if (!submitted) setTimeout(tick, 1000);
    };
    tick();
  }

  // ------------------------------------------------------------ collect results
  // a cell's visible value: form controls inside observation tables contribute their current value
  function cellText(c) {
    var ctl = c.querySelectorAll('input, select, textarea');
    if (!ctl.length) return txt(c).slice(0, 60);
    return Array.prototype.map.call(ctl, function (el) {
      if (el.tagName === 'SELECT') { var o = el.options[el.selectedIndex]; return o && el.value !== '' ? o.text : ''; }
      if (el.type === 'checkbox' || el.type === 'radio') return el.checked ? (el.value || '✓') : '';
      return el.value;
    }).filter(Boolean).join(' ').slice(0, 60);
  }
  function tablesOf(root) {
    var out = [];
    (root ? root.querySelectorAll('table') : []).forEach(function (t, ti) {
      if (ti >= 8) return;
      var rows = [];
      t.querySelectorAll('tr').forEach(function (tr, ri) { if (ri < 80) rows.push(Array.prototype.slice.call(tr.children, 0, 16).map(cellText)); });
      if (rows.length > 1) out.push(rows);
    });
    return out;
  }
  function results() {
    try { if (typeof renderObservation === 'function') renderObservation(); } catch (e) { }
    try {
      if (typeof buildResults === 'function') { var r = buildResults(); if (r && r.rows) return { rows: r.rows.map(function (x) { return [String(x[0]).replace(/<[^>]+>/g, ''), String(x[1]).replace(/<[^>]+>/g, '')]; }), text: String(r.text || '').replace(/<[^>]+>/g, '') }; }
    } catch (e) { }
    try {
      if (typeof openResultsModal === 'function') {
        openResultsModal();
        var body = document.getElementById('resBody'), rows = [];
        if (body) body.querySelectorAll(':scope > div').forEach(function (d) { var s = d.querySelectorAll('span'); if (s.length >= 2) rows.push([txt(s[0]), txt(s[s.length - 1])]); });
        var m = document.getElementById('modalResults'); if (m) m.classList.add('hidden');
        if (rows.length) return { rows: rows, text: txt(document.getElementById('resExplanation')) };
      }
    } catch (e) { }
    return null;
  }
  function viva() {
    var q = null;
    try { q = (typeof QUIZ !== 'undefined' && Array.isArray(QUIZ)) ? QUIZ : null; } catch (e) { }
    if (q) {
      var items = q.map(function (it, i) {
        var c = document.querySelector('input[name="q' + i + '"]:checked'); var ch = c ? +c.value : null;
        var strip = function (s) { return String(s || '').replace(/<[^>]+>/g, ''); };
        return { i: i, q: strip(it.q).slice(0, 200), chosen: ch === null ? '' : strip(it.o[ch]).slice(0, 120), correct: strip(it.o[it.a]).slice(0, 120), ok: ch === it.a };
      });
      return { score: items.filter(function (x) { return x.ok; }).length, total: items.length, answered: items.filter(function (x) { return x.chosen !== ''; }).length, items: items };
    }
    if (window.MCP_VIVA_LAST) return { score: window.MCP_VIVA_LAST.score, total: window.MCP_VIVA_LAST.total, answered: window.MCP_VIVA_LAST.total };
    var disp = document.getElementById('vivaScoreDisplay'), m = disp && /(\d+)\s*\/\s*(\d+)/.exec(txt(disp));
    if (m) return { score: +m[1], total: +m[2], answered: +m[2] };
    var names = {}; document.querySelectorAll('#modalQuestions input[type=radio], [id*=iva] input[type=radio]').forEach(function (r) { names[r.name] = 1; });
    var n = Object.keys(names).length;
    return n ? { score: 0, total: n, answered: 0, note: 'viva not submitted' } : null;
  }
  function inputs() {
    var o = {}; document.querySelectorAll('#viewObservation input:not([type=button]):not([type=submit]):not([type=radio]):not([type=checkbox]), #viewObservation select').forEach(function (el) { if (el.id && el.value !== '') o[el.id] = String(el.value).slice(0, 80); });
    return o;
  }
  function collect() {
    var obs = document.getElementById('viewObservation');
    var tables = tablesOf(obs), res = results(), v = viva(), ans = null;
    try { ans = typeof window.MCP_PROBE === 'function' ? window.MCP_PROBE() : null; } catch (e) { }
    var numericCells = 0;
    tables.forEach(function (t) { t.slice(1).forEach(function (r) { r.forEach(function (c) { if (/\d/.test(c) && !/^[—–-]+$/.test(c)) numericCells++; }); }); });
    var resNumbers = res ? res.rows.filter(function (r) { return /\d/.test(r[1]) && !/^\s*(—|--|-)\s*$/.test(r[1]); }).length : 0;
    var inf = [txt(document.getElementById('lblInference')), txt(document.getElementById('lblInferenceDetail'))].filter(Boolean).join(' • ');
    return {
      results: res, tables: tables, inference: inf.slice(0, 1500), viva: v, inputs: inputs(),
      answer: ans && ans.truth != null ? { given: ans.given, truth: ans.truth, kind: ans.kind, tol: ans.tol } : null,
      completion: numericCells >= 6 || resNumbers >= 2,
      client: { elapsed_s: Math.round((Date.now() - startedAt) / 1000), ua: navigator.userAgent.slice(0, 120) }
    };
  }

  // ------------------------------------------------------------ modal + submit
  var modal = h('div', { class: 'fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[60] hidden flex items-center justify-center p-4', id: 'mcpModal', role: 'dialog', 'aria-modal': 'true' });
  document.body.appendChild(modal);
  function show(html) { modal.innerHTML = '<div class="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-slate-200 text-slate-800">' + html + '</div>'; modal.classList.remove('hidden'); }
  function hide() { modal.classList.add('hidden'); }
  modal.addEventListener('click', function (e) { if (e.target === modal && !busy) hide(); });

  function openConfirm() {
    if (submitted) return;
    var d = collect();
    var warn = [];
    if (!d.completion) warn.push('Your observation sheet looks empty or incomplete.');
    if (d.viva && d.viva.answered < d.viva.total) warn.push('Viva: ' + d.viva.answered + ' of ' + d.viva.total + ' questions answered' + (d.viva.note ? ' (open the viva and press Submit first)' : '') + '.');
    if (d.answer && (d.answer.given === '' || d.answer.given == null)) warn.push('You have not entered your answer / deduction for the unknown.');
    show('<div class="flex items-center justify-between border-b pb-3"><h3 class="text-base font-bold">Submit to your faculty?</h3><button data-x class="text-slate-400 hover:text-slate-600 text-lg font-bold" aria-label="Close">✕</button></div>' +
      '<p class="text-xs text-slate-600">Your observation tables, results, viva answers' + (d.answer ? ' and answer for the unknown' : '') + ' will be saved for <b>' + esc(C.title) + '</b>. ' + (C.maxAttempts - C.attemptNo > 0 ? 'You will have ' + (C.maxAttempts - C.attemptNo) + ' more attempt(s) after this.' : '<b>This is your last attempt.</b>') + '</p>' +
      (warn.length ? '<ul class="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-3 list-disc pl-6 space-y-1">' + warn.map(function (w) { return '<li>' + esc(w) + '</li>'; }).join('') + '</ul>' : '<p class="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg p-3">Everything looks complete.</p>') +
      '<div class="flex justify-end gap-2 pt-2 border-t"><button data-x class="px-4 py-2 border rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100">Keep working</button><button data-go class="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow">Submit now</button></div>');
    modal.querySelectorAll('[data-x]').forEach(function (b) { b.onclick = hide; });
    modal.querySelector('[data-go]').onclick = function () { doSubmit(false); };
  }

  function doSubmit(auto) {
    if (submitted || busy) return;
    busy = true;
    var payload = collect();
    show('<div class="text-center py-6 space-y-2"><div class="w-10 h-10 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto"></div><p class="text-sm font-semibold">' + (auto ? 'Time is up: submitting…' : 'Submitting…') + '</p></div>');
    fetch(C.submitUrl, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': C.csrf }, body: JSON.stringify(payload) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }, function () { return { ok: false, j: { error: 'Server error (' + r.status + ')' } }; }); })
      .then(function (res) {
        busy = false;
        if (!res.ok) {
          show('<h3 class="text-base font-bold text-rose-700">Could not submit</h3><p class="text-sm text-slate-700">' + esc(res.j.error || 'Unknown error') + '</p><div class="flex justify-end"><button data-x class="px-4 py-2 bg-slate-800 text-white text-xs font-semibold rounded-lg">Close</button></div>');
          modal.querySelector('[data-x]').onclick = hide;
          if (res.j.error && /already been submitted/.test(res.j.error)) lockSubmitted();
          return;
        }
        lockSubmitted();
        var j = res.j;
        show('<div class="text-center space-y-1"><div class="text-4xl">✅</div><h3 class="text-lg font-bold">Submitted</h3><p class="text-xs text-slate-500">' + (j.late ? 'Marked late. ' : '') + (j.timed_out ? 'Submitted after the time limit. ' : '') + 'Your faculty can now review it.</p></div>' +
          '<div class="grid grid-cols-3 gap-2 text-center"><div class="p-2 rounded-lg bg-slate-50 border"><div class="text-[10px] uppercase text-slate-500 font-mono">Viva</div><div class="font-bold mono">' + (j.viva[1] ? j.viva[0] + '/' + j.viva[1] : '—') + '</div></div>' +
          '<div class="p-2 rounded-lg bg-slate-50 border"><div class="text-[10px] uppercase text-slate-500 font-mono">Answer</div><div class="font-bold mono">' + (j.answer_ok === null ? '—' : j.answer_ok ? '✓' : '✗') + '</div></div>' +
          '<div class="p-2 rounded-lg bg-teal-50 border border-teal-200"><div class="text-[10px] uppercase text-teal-700 font-mono">Provisional</div><div class="font-bold mono text-teal-800">' + j.marks + '/' + j.max_marks + '</div></div></div>' +
          '<p class="text-[11px] text-slate-500">Provisional marks are calculated automatically; your faculty may change them.</p>' +
          '<div class="flex justify-end gap-2"><button data-x class="px-4 py-2 border rounded-lg text-xs font-semibold text-slate-600">Stay on this page</button><a href="' + esc(C.backUrl || C.home) + '" class="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-lg shadow">Back to my assignment</a></div>');
        modal.querySelector('[data-x]').onclick = hide;
      })
      .catch(function () {
        busy = false;
        show('<h3 class="text-base font-bold text-rose-700">Network problem</h3><p class="text-sm text-slate-700">Your work has not been sent. Check your connection and press <b>Retry</b>. Do not close this page.</p><div class="flex justify-end gap-2"><button data-x class="px-4 py-2 border rounded-lg text-xs font-semibold">Close</button><button data-go class="px-4 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-lg">Retry</button></div>');
        modal.querySelector('[data-x]').onclick = hide;
        modal.querySelector('[data-go]').onclick = function () { doSubmit(auto); };
      });
  }
  function lockSubmitted() {
    submitted = true;
    var b = document.getElementById('mcpSubmit');
    if (b) { b.disabled = true; b.textContent = 'Submitted ✓'; b.className = 'px-3 py-1 rounded-md bg-slate-600 text-white font-bold cursor-default'; }
    var t = document.getElementById('mcpTimer'); if (t) t.textContent = 'done';
  }
  window.MCP_BRIDGE = { collect: collect, submit: function () { doSubmit(false); }, ctx: C };
})();
