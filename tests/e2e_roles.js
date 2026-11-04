// End-to-end test: every role, through nginx → gunicorn → PostgreSQL, in Chromium.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:8095';
const OUT = '/tmp/e2e'; fs.mkdirSync(OUT, { recursive: true });
const results = []; let shot = 0;
const ok = (name, cond, extra = '') => { results.push([cond ? 'PASS' : 'FAIL', name, extra]); console.log(`${cond ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };

(async () => {
  const browser = await chromium.launch();
  const external = [];
  async function newCtx() {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 }, acceptDownloads: true });
    await ctx.route('**/*', r => { const u = r.request().url(); if (u.startsWith(BASE) || u.startsWith('data:') || u.startsWith('blob:')) return r.continue(); external.push(u); return r.abort(); });
    const p = await ctx.newPage();
    p.errors = [];
    p.on('pageerror', e => p.errors.push(e.message));
    p.on('console', m => { if (m.type() === 'error' && !/favicon/.test(m.text())) p.errors.push('console: ' + m.text()); });
    p.on('dialog', d => d.accept());
    return { ctx, p };
  }
  const snap = async (p, name) => p.screenshot({ path: `${OUT}/${String(++shot).padStart(2, '0')}_${name}.png`, fullPage: true });
  const msgText = async p => (await p.$$eval('[role=status]', els => els.map(e => e.innerText).join(' | '))).trim();
  const tempPw = async p => { const m = /Temporary password: (\S+)/.exec(await msgText(p)); return m ? m[1] : null; };
  async function login(p, user, pw) {
    await p.goto(BASE + '/accounts/login/');
    await p.fill('#id_username', user); await p.fill('#id_password', pw);
    await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Sign in")')]);
  }
  async function gates(p, newPw) {
    for (let i = 0; i < 3; i++) {
      if (p.url().includes('/accounts/password/force/')) {
        await p.fill('#id_new_password1', newPw); await p.fill('#id_new_password2', newPw);
        await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Save password")')]);
      } else if (p.url().includes('/consent/')) {
        await p.check('#id_accept'); await p.check('#id_age_ok');
        await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Accept and continue")')]);
      } else break;
    }
  }
  async function logout(p) { await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Sign out")')]); }

  // ---------------------------------------------------------------- 1. visitor
  let { ctx, p } = await newCtx();
  await p.goto(BASE + '/modules/');
  ok('visitor: catalogue shows 27 experiments', (await p.$$('.expCard')).length === 27);
  ok('visitor: 4 demo cards', (await p.$$('text=Demo • no login')).length === 4);
  await snap(p, 'landing');
  await p.click('a.expCard:has-text("Routes of Drug Administration")'); await p.waitForTimeout(800);
  ok('visitor: demo experiment opens with DEMO bar', (await p.textContent('#mcpBar')).includes('DEMO'));
  ok('visitor: header shows Guest', (await p.content()).includes('Guest (demo mode)'));
  await snap(p, 'demo_experiment');
  await p.goto(BASE + '/experiments/18-pa2-value-schild-plot.html');
  ok('visitor: locked experiment redirects to sign-in', p.url().includes('/accounts/login/?next='));
  for (const u of ['/privacy/', '/terms/', '/conditions/']) { await p.goto(BASE + u); ok(`visitor: ${u} renders`, (await p.textContent('article')).length > 2000); }
  await snap(p, 'conditions');
  ok('visitor: no JS errors', p.errors.length === 0, p.errors.join(' | '));
  await ctx.close();

  // ---------------------------------------------------------------- 2. super admin creates a college
  ({ ctx, p } = await newCtx());
  await login(p, 'superadmin', 'Super@Admin2026'); await gates(p, 'Super@Admin2026');
  ok('super admin: lands on platform dashboard', p.url().endsWith('/platform/'));
  await p.goto(BASE + '/platform/colleges/new/');
  await p.fill('#id_name', 'E2E College of Pharmacy'); await p.fill('#id_code', 'e2e'); await p.fill('#id_location_text', 'Dwarka New Delhi');
  await p.fill('#id_grievance_officer', 'Prof. Grievance'); await p.fill('#id_grievance_email', 'griev@e2e.example');
  await p.fill('#id_admin_first_name', 'Asha'); await p.fill('#id_admin_last_name', 'Admin');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Save")')]);
  const caPw = await tempPw(p);
  ok('super admin: college + admin created', !!caPw && (await msgText(p)).includes('e2e-admin'));
  await snap(p, 'platform_colleges');
  ok('super admin: no JS errors', p.errors.length === 0, p.errors.join(' | '));
  await ctx.close();

  // ---------------------------------------------------------------- 3. college admin adds staff
  ({ ctx, p } = await newCtx());
  await login(p, 'e2e-admin', caPw);
  ok('college admin: forced to change temporary password', p.url().includes('/accounts/password/force/'));
  await gates(p, 'Asha@College2026');
  ok('college admin: lands on college dashboard', p.url().endsWith('/college/'));
  ok('college admin: header shows college location', (await p.textContent('header')).includes('Dwarka New Delhi'));
  await p.goto(BASE + '/college/users/');
  const addStaff = async (first, last, uname, role) => {
    await p.fill('#id_first_name', first); await p.fill('#id_last_name', last); await p.fill('#id_username', uname); await p.selectOption('#id_role', role);
    await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Create account")')]);
    return tempPw(p);
  };
  const facPw = await addStaff('Vara', 'Prasad', 'vprasad', 'faculty');
  const laPw = await addStaff('Lab', 'Helper', 'labhelper', 'lab_assistant');
  ok('college admin: faculty + lab assistant created', !!facPw && !!laPw);
  await snap(p, 'college_people');
  await p.goto(BASE + '/college/experiments/');
  await p.uncheck('input[name=enabled][value="3"]');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Save")')]);
  ok('college admin: experiment 3 switched off', (await msgText(p)).includes('24 experiments enabled'));
  ok('college admin: no JS errors', p.errors.length === 0, p.errors.join(' | '));
  await ctx.close();

  // ---------------------------------------------------------------- 4. faculty: batch, CSV, assignments
  ({ ctx, p } = await newCtx());
  await login(p, 'e2e-vprasad', facPw); await gates(p, 'Vara@Faculty2026');
  ok('faculty: lands on dashboard', p.url().endsWith('/faculty/'));
  await p.goto(BASE + '/faculty/batches/new/');
  await p.fill('#id_name', 'B.Pharm Section A');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Save")')]);
  const batchUrl = p.url();
  const classCode = (await p.textContent('.tracking-widest')).trim();
  ok('faculty: batch created with class code', /^[A-Z0-9]{8}$/.test(classCode), classCode);
  fs.writeFileSync('/tmp/e2e/students.csv', 'roll_no,first_name,last_name,email\nBP001,Riya,Sharma,riya@example.com\nBP002,Arjun,Mehta,\n');
  await p.setInputFiles('input[name=file]', '/tmp/e2e/students.csv');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Upload & enrol")')]);
  ok('faculty: CSV created 2 accounts', (await msgText(p)).includes('2 new student account'));
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('a:has-text("Download new students")')]);
  const creds = fs.readFileSync(await dl.path(), 'utf8');
  const credOf = roll => creds.split('\n').find(l => l.startsWith(roll)).split(',');
  const [, , s1user, s1pw] = credOf('BP001'); const [, , s2user, s2pw] = credOf('BP002');
  ok('faculty: credentials sheet downloaded', s1user === 'e2e-bp001' && !!s1pw);
  const assign = async (expNo, exam) => {
    await p.goto(batchUrl); await p.click('a:has-text("Assign experiment")');
    await p.selectOption('#id_experiment', { label: (await p.$$eval('#id_experiment option', (os, n) => os.find(o => o.textContent.startsWith(`Exp ${String(n).padStart(2, '0')}`)).textContent, expNo)) });
    await p.fill('#id_instructions', exam ? 'Exam: work alone.' : 'Record all four curves and report pA2.');
    await p.fill('#id_max_marks', '10'); await p.fill('#id_max_attempts', exam ? '1' : '2');
    if (exam) { await p.check('#id_exam_mode'); await p.fill('#id_time_limit_min', '30'); }
    await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Save")')]);
    return (await msgText(p)).includes('Assignment saved');
  };
  ok('faculty: practical assignment (Exp 18) created', await assign(18, false));
  ok('faculty: exam assignment (Exp 14, 30 min) created', await assign(14, true));
  const expOpts = await p.goto(batchUrl.replace(/\/$/, '') + '/assignments/new/').then(() => p.$$eval('#id_experiment option', os => os.map(o => o.textContent)));
  ok('faculty: disabled Exp 3 not assignable', !expOpts.some(t => t.startsWith('Exp 03')));
  await p.goto(batchUrl); await snap(p, 'faculty_batch');
  ok('faculty: no JS errors', p.errors.length === 0, p.errors.join(' | '));
  const facCtx = { ctx, p };

  // ---------------------------------------------------------------- 5. student 1: practical + exam
  ({ ctx, p } = await newCtx());
  await login(p, s1user, s1pw);
  ok('student: forced password change', p.url().includes('/accounts/password/force/'));
  await gates(p, 'Riya@Student2026');
  ok('student: lands on assignments', p.url().endsWith('/student/'));
  ok('student: sees 2 assignments', (await p.$$('text=/EXP #1[48]/')).length >= 2);
  await snap(p, 'student_dashboard');
  await p.click('a:has-text("Start")'); await p.waitForTimeout(1200);   // first in due order
  let bar = await p.textContent('#mcpBar');
  const isExamFirst = bar.includes('EXAM');
  async function doPractical() {
    ok('student: assignment bar visible', (await p.textContent('#mcpBar')).includes('ASSIGNMENT'));
    ok('student: header shows student name', (await p.content()).includes('Riya Sharma'));
    await p.evaluate(() => { runAll(); switchTab('observation'); QUIZ.forEach((q, i) => { const r = document.querySelector(`input[name="q${i}"][value="${q.a}"]`); if (r) r.checked = true; }); document.getElementById('answerIn').value = TRUE_PA2; });
    await p.waitForTimeout(400); await snap(p, 'student_exp18_obs');
    await p.click('#mcpSubmit'); await p.waitForSelector('#mcpModal:not(.hidden)');
    ok('student: confirm dialog says complete', (await p.textContent('#mcpModal')).includes('Everything looks complete'));
    await p.click('#mcpModal [data-go]'); await p.waitForSelector('#mcpModal >> text=Submitted', { timeout: 10000 });
    const txt = await p.textContent('#mcpModal');
    ok('student: submitted with full provisional marks', /10\/10/.test(txt), txt.replace(/\s+/g, ' ').slice(0, 120));
    await snap(p, 'student_submitted');
  }
  async function doExam() {
    const st = await p.evaluate(() => ({
      exam: document.getElementById('mcpBar').innerText,
      refHidden: [...document.querySelectorAll('button')].filter(b => /Reference Dataset/i.test(b.innerText)).every(b => b.offsetParent === null),
      guidedHidden: [...document.querySelectorAll('button')].filter(b => /Guided run/i.test(b.innerText)).every(b => b.offsetParent === null),
      skipHidden: [...document.querySelectorAll('button')].filter(b => /Skip waiting/i.test(b.innerText)).every(b => b.offsetParent === null || b.closest('.hidden')),
      verifyHidden: [...document.querySelectorAll('button')].filter(b => /^Verify/i.test(b.innerText.trim())).every(b => b.style.display === 'none'),
      resultsHidden: [...document.querySelectorAll('button')].filter(b => /Results/i.test(b.innerText)).every(b => b.style.display === 'none'),
      vivaNeutral: (() => { QUIZ.forEach((q, i) => { const r = document.querySelector(`input[name="q${i}"][value="${q.a}"]`); if (r) r.checked = true; }); evaluateQuestions(); return /saved and will be marked/.test(document.getElementById('quizScore').innerText) && !/Viva score/.test(document.getElementById('modalQuestions').innerText); })(),
    }));
    ok('exam: EXAM badge + timer', /EXAM/.test(st.exam) && /\d\d:\d\d/.test(st.exam), st.exam.replace(/\s+/g, ' '));
    ok('exam: reference dataset / guided run / skip hidden', st.refHidden && st.guidedHidden && st.skipHidden);
    ok('exam: answer Verify + Results buttons hidden', st.verifyHidden && st.resultsHidden);
    ok('exam: viva records answers without revealing marks', st.vivaNeutral);
    const n0 = await p.evaluate(() => { guidedRun(); loadReferenceDataset(); return OB.responses.length; });
    ok('exam: blocked shortcuts do nothing when called', n0 === 0);
    await p.evaluate(() => { [0.05, 0.1, 0.2, 0.4, 0.8].forEach(giveS); giveT(0.2); giveT(0.3); OB.finishInstant(); switchTab('observation'); document.getElementById('answerIn').value = (TRUE_T * 1.04).toFixed(3); });
    await snap(p, 'student_exam');
    await p.click('#mcpSubmit'); await p.waitForSelector('#mcpModal:not(.hidden)');
    await p.click('#mcpModal [data-go]'); await p.waitForSelector('#mcpModal >> text=Submitted', { timeout: 10000 });
    const exTxt = await p.textContent('#mcpModal');
    ok('exam: submitted, answer within 10% accepted, viva scored', exTxt.includes('✓') && /Viva7\/7/.test(exTxt.replace(/\s+/g, '')), exTxt.replace(/\s+/g, ' ').slice(0, 100));
  }
  if (isExamFirst) { await doExam(); } else { await doPractical(); }
  await p.goto(BASE + '/student/');
  await p.click('a:has-text("Start")'); await p.waitForTimeout(1200);
  if (isExamFirst) { await doPractical(); } else { await doExam(); }
  await p.goto(BASE + '/student/');
  ok('student: both assignments submitted', (await p.$$('text=Submitted')).length >= 2);
  ok('student (1): no JS errors during experiments', p.errors.length === 0, p.errors.join(' | '));
  await p.goto(BASE + '/experiments/03-anticonvulsant-activity-mes-electroconvulsometer.html');
  ok('student: disabled Exp 3 refused', (await p.textContent('main')).includes('switched off'));
  ok('student: faculty pages forbidden', (await p.goto(BASE + '/faculty/')).status() === 403);
  const s1 = { ctx, p };

  // ---------------------------------------------------------------- 6. new student via class code
  ({ ctx, p } = await newCtx());
  await p.goto(BASE + `/accounts/signup/?code=${classCode}`);
  await p.fill('#id_first_name', 'Neha'); await p.fill('#id_last_name', 'Verma'); await p.fill('#id_roll_no', 'BP003');
  await p.fill('#id_password1', 'Neha@Student2026'); await p.fill('#id_password2', 'Neha@Student2026');
  await p.check('#id_accept'); await p.check('#id_age_ok');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Create my account")')]);
  ok('class-code sign-up: account created and enrolled', p.url().endsWith('/student/') && (await msgText(p)).includes('e2e-bp003'));
  await p.goto(BASE + '/me/data/');
  const [dd] = await Promise.all([p.waitForEvent('download'), p.click('a:has-text("Download all my data")')]);
  const mine = JSON.parse(fs.readFileSync(await dd.path(), 'utf8'));
  ok('data rights: JSON export has account + consent', mine.account.username === 'e2e-bp003' && mine.consents.length === 1);
  await p.selectOption('#id_kind', 'deletion'); await p.fill('#id_message', 'Testing deletion');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Send request")')]);
  ok('data rights: deletion request sent', (await msgText(p)).includes('Request received'));
  ok('student (3): no JS errors', p.errors.length === 0, p.errors.join(' | '));
  await ctx.close();

  // ---------------------------------------------------------------- 7. faculty grades + exports
  ({ ctx, p } = facCtx);
  await p.goto(BASE + '/faculty/');
  ok('faculty: 2 submissions waiting', (await p.textContent('main')).includes('Waiting for grading') && (await p.$$('a:has-text("Grade →")')).length === 2);
  await p.click('a:has-text("Grade →")');
  await p.waitForLoadState('load');
  ok('faculty: submission shows observation data', (await p.$$('table')).length >= 1);
  await snap(p, 'faculty_grading');
  await p.fill('#id_manual_marks', '9'); await p.fill('#id_feedback', 'Well done: clear Schild analysis.');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Save grade")')]);
  ok('faculty: graded', (await msgText(p)).includes('Graded'));
  await p.goto(batchUrl + 'marks/');
  await snap(p, 'faculty_marks');
  const [x] = await Promise.all([p.waitForEvent('download'), p.click('a:has-text("Excel")')]);
  ok('faculty: Excel marks sheet downloaded', (await x.suggestedFilename()).endsWith('.xlsx') && fs.statSync(await x.path()).size > 3000);
  ok('faculty: no JS errors', p.errors.length === 0, p.errors.join(' | '));
  await ctx.close();

  // ---------------------------------------------------------------- 8. student sees feedback
  ({ ctx, p } = s1);
  await p.goto(BASE + '/student/');
  ok('student: graded marks + feedback visible', (await p.textContent('main')).includes('Graded'));
  await ctx.close();

  // ---------------------------------------------------------------- 9. lab assistant
  ({ ctx, p } = await newCtx());
  await login(p, 'e2e-labhelper', laPw); await gates(p, 'Pipette#Kymograph91');
  ok('lab assistant: dashboard', p.url().endsWith('/faculty/'));
  await p.goto(batchUrl);
  ok('lab assistant: can enrol, cannot assign', !!(await p.$('button:has-text("Add student")')) && !(await p.$('a:has-text("Assign experiment")')));
  ok('lab assistant: no JS errors', p.errors.length === 0, p.errors.join(' | '));
  ok('lab assistant: export forbidden', (await p.goto(batchUrl + 'marks/?format=xlsx')).status() === 403);
  await ctx.close();

  // ---------------------------------------------------------------- 10. college admin handles deletion + audit
  ({ ctx, p } = await newCtx());
  await login(p, 'e2e-admin', 'Asha@College2026');
  await p.goto(BASE + '/college/requests/');
  await Promise.all([p.waitForLoadState('load'), p.click('button:has-text("Erase data")')]);
  ok('college admin: deletion completed', (await msgText(p)).includes('completed'));
  await p.goto(BASE + '/college/audit/');
  const audit = await p.textContent('main');
  ok('audit log records key actions', ['login', 'students_uploaded', 'attempt_submitted', 'attempt_graded', 'data_request_done', 'marks_exported'].every(a => audit.includes(a)));
  await snap(p, 'audit');
  ok('college admin: no JS errors', p.errors.length === 0, p.errors.join(' | '));
  await ctx.close();
  // erased account cannot sign in
  ({ ctx, p } = await newCtx());
  await login(p, 'e2e-bp003', 'Neha@Student2026');
  ok('erased account cannot sign in', p.url().includes('/accounts/login/'));
  await ctx.close();

  ok('no external network requests', external.length === 0, external.slice(0, 3).join(' '));
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 1));
  const fails = results.filter(r => r[0] === 'FAIL');
  console.log(`\n${results.length - fails.length}/${results.length} checks passed`);
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error('E2E CRASH', e); process.exit(2); });
