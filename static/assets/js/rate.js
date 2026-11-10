/* XPRISM: feedback after an experiment.
   reportHtml() draws the report a student reads after submitting (what each part earned, what to revise).
   mount() puts the "Rate this experiment" form into a box and sends it to the server.
   Used by bridge.js on the benches and by the student's assignment page. Styles: the .fb-* rules in theme.css. */
window.XPFeedback = (function () {
  'use strict';
  var n = 0;
  var STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.6l2.85 6.05 6.55.85-4.8 4.6 1.25 6.6L12 17.45 6.150 20.700l1.250-6.600-4.800-4.600 6.550-.850z"/></svg>';
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function num(v) { return v == null ? '—' : String(Math.round(v * 10) / 10); }

  function reportHtml(r, o) {
    o = o || {};
    var parts = (r.parts || []).map(function (p) {
      return '<li class="fb-part fb-' + esc(p.state) + '"><h3>' + esc(p.label) + '<span>' + esc(p.share) + '% of the score</span></h3><span class="fb-val">' + esc(p.value) + '</span>' +
        '<div class="fb-bar"><i style="width:' + (+p.pct || 0) + '%"></i></div><p>' + esc(p.advice) + '</p></li>';
    }).join('');
    var more = (r.notes || []).map(function (t) { return '<p class="fb-note">' + esc(t) + '</p>'; }).join('');
    if (r.revise && r.revise.length) {
      more += '<details class="fb-revise"><summary>Viva questions to revise (' + r.revise.length + ')</summary><ol>' + r.revise.map(function (q) {
        return '<li><b>' + esc(q.q) + '</b><span>Your answer: ' + (q.chosen ? esc(q.chosen) : 'not answered') + '</span><span class="fb-right">Correct answer: ' + esc(q.correct) + '</span></li>';
      }).join('') + '</ol></details>';
    }
    if (r.attempts_left > 0) more += '<p class="fb-left">You have ' + r.attempts_left + ' more attempt' + (r.attempts_left === 1 ? '' : 's') + '. Your best attempt counts.</p>';
    return '<section class="fb-report"><div class="fb-top"><div><h2>' + esc(r.headline) + '</h2><p>' + esc(o.status || '') + '</p></div>' +
      '<div class="fb-marks">' + num(r.marks) + '<span>/' + num(r.max_marks) + '</span><small>' + (r.provisional ? 'Provisional marks' : 'Marks from your faculty') + '</small></div></div>' +
      '<ul class="fb-parts">' + parts + '</ul>' + (more ? '<div class="fb-more">' + more + '</div>' : '') + '</section>';
  }

  // o: { url, csrf, attempt (optional), heading (optional) }
  function mount(box, o) {
    var id = 'fbr' + (++n), stars = '';
    for (var v = 5; v >= 1; v--) stars += '<input type="radio" name="rating" value="' + v + '" id="' + id + 's' + v + '"><label for="' + id + 's' + v + '" title="' + v + ' out of 5"><span class="sr-only">' + v + ' out of 5</span>' + STAR + '</label>';
    var diff = [['easy', 'Too easy'], ['right', 'About right'], ['hard', 'Too hard']].map(function (d) {
      return '<input type="radio" name="difficulty" value="' + d[0] + '" id="' + id + d[0] + '"><label for="' + id + d[0] + '">' + d[1] + '</label>';
    }).join('');
    box.innerHTML = '<form class="fb-rate" novalidate><h3>' + esc(o.heading || 'Rate this experiment') + '</h3><p>Your faculty and the XPRISM team see ratings without your name.</p>' +
      '<fieldset><legend>Overall</legend><div class="fb-stars">' + stars + '</div></fieldset>' +
      '<fieldset><legend>How hard was it?</legend><div class="fb-diff">' + diff + '</div></fieldset>' +
      '<fieldset><label class="fb-lab" for="' + id + 'c">What would make it better? (optional)</label><textarea id="' + id + 'c" name="comment" rows="3" maxlength="1000"></textarea></fieldset>' +
      '<div class="fb-send"><button type="submit">Send feedback</button><p role="status"></p></div></form>';
    var form = box.querySelector('form'), msg = form.querySelector('[role=status]'), btn = form.querySelector('button');
    function say(t, bad) { msg.textContent = t; msg.className = bad ? 'is-error' : ''; }
    form.addEventListener('change', function () { say(''); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var r = form.querySelector('input[name=rating]:checked'), d = form.querySelector('input[name=difficulty]:checked');
      if (!r) { say('Choose a star rating first.', true); return; }
      btn.disabled = true; say('Sending…');
      fetch(o.url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': o.csrf },
        body: JSON.stringify({ rating: +r.value, difficulty: d ? d.value : '', comment: form.comment.value, attempt: o.attempt || null }) })
        .then(function (res) { return res.json().then(function (j) { return { ok: res.ok, j: j }; }, function () { return { ok: false, j: {} }; }); })
        .then(function (res) {
          if (res.ok) { box.innerHTML = '<div class="fb-rate"><p class="fb-thanks" role="status">Feedback sent. Thank you.</p></div>'; if (o.done) o.done(); return; }
          btn.disabled = false; say(res.j.error || 'Feedback was not sent. Try again.', true);
        })
        .catch(function () { btn.disabled = false; say('Feedback was not sent: check your connection and try again.', true); });
    });
  }
  return { reportHtml: reportHtml, mount: mount };
})();
