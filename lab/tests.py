import datetime
import io
import json
import re
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from .free_year import one_year_after
from .models import Assignment, Attempt, AuditLog, Batch, College, ConsentRecord, DataRequest, Enrollment, Experiment, FreeYearApplication, FreeYearInvitation, Role, TrialVisit, User
from .views_auth import anonymise_user

PW = 'Str0ng!Passw0rd'


def mkuser(username, role, college=None, consent=True, ethics=True, **kw):
    u = User(username=username, role=role, college=college, first_name=username.title(), **kw)
    if consent:
        u.consent_version, u.consent_at = settings.POLICY_VERSION, timezone.now()
    if ethics:
        u.ethics_version, u.ethics_at = settings.ETHICS_VERSION, timezone.now()
    u.set_password(PW)
    u.save()
    return u


def ctx_of(resp):
    m = re.search(rb'<script id="mcp-ctx" type="application/json">(.*?)</script>', resp.content)
    return json.loads(m.group(1)) if m else None


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('bootstrap_lab', verbosity=0)
        cls.c1 = College.objects.create(name='College One', code='one', location_text='Campus One')
        cls.c2 = College.objects.create(name='College Two', code='two')
        cls.sa = mkuser('root', Role.SUPERADMIN, is_superuser=True)
        cls.ca = mkuser('one-admin', Role.COLLEGE_ADMIN, cls.c1)
        cls.ca2 = mkuser('two-admin', Role.COLLEGE_ADMIN, cls.c2)
        cls.fac = mkuser('one-fac', Role.FACULTY, cls.c1)
        cls.fac_other = mkuser('one-fac2', Role.FACULTY, cls.c1)
        cls.la = mkuser('one-la', Role.LAB_ASSISTANT, cls.c1)
        cls.st = mkuser('one-bp001', Role.STUDENT, cls.c1, roll_no='BP001')
        cls.st2 = mkuser('one-bp002', Role.STUDENT, cls.c1, roll_no='BP002')
        cls.batch = Batch.objects.create(college=cls.c1, name='Section A', created_by=cls.fac)
        cls.batch.faculty.add(cls.fac)
        Enrollment.objects.create(batch=cls.batch, student=cls.st)
        Enrollment.objects.create(batch=cls.batch, student=cls.st2)
        cls.e18 = Experiment.objects.get(no=18)
        cls.e14 = Experiment.objects.get(no=14)
        cls.a = Assignment.objects.create(batch=cls.batch, experiment=cls.e18, due_at=timezone.now() + timezone.timedelta(days=3), max_marks=10, max_attempts=2, created_by=cls.fac)

    def login(self, u):
        self.client.force_login(u)


class PublicTests(Base):
    def test_landing_and_legal(self):
        for url in ['/', '/privacy/', '/terms/', '/conditions/', '/accounts/login/', '/accounts/signup/', '/healthz']:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get('/index.html').status_code, 301)
        r = self.client.get('/privacy/')
        self.assertContains(r, 'Digital Personal Data Protection Act, 2023')
        self.assertContains(r, settings.LEGAL['grievance_email'])

    def test_visitors_must_sign_in_for_every_experiment(self):
        r = self.client.get(Experiment.objects.get(no=1).url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])
        self.assertContains(self.client.get('/'), 'Start free trial')
        self.assertEqual(self.client.get('/experiments/no-such-thing.html').status_code, 404)
        for url in ['/ethics/', '/about/', '/subscribe/', '/accounts/trial/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get('/ethics/'), 'CCSEA')
        about = self.client.get('/about/')
        for text in ['XPRISM', 'Experimental Pharmacology Research &amp; Interactive Student Module', 'Dr. Vara Prasad Saka', 'Aaron Innovations', 'drvaraprasadsaka@gmail.com']:
            self.assertContains(about, text)
        self.assertContains(self.client.get('/'), 'Created by Dr. Vara Prasad Saka')
        self.assertNotContains(self.client.get('/'), 'MyCAL')

    def test_home_modules_and_documentation_are_public(self):
        home = self.client.get('/')
        for text in ['Replacement', 'Reduction', 'Refinement', 'Explore our 3Rs commitment', '/accounts/trial/', '/accounts/signup/', '/accounts/login/', '/modules/', '/documentation/']:
            self.assertContains(home, text)
        self.assertContains(home, 'class="expCard', count=6)
        self.assertContains(self.client.get('/modules/'), 'class="expCard', count=37)
        docs = self.client.get('/documentation/')
        self.assertContains(docs, 'id="exp-18"')
        self.assertContains(docs, 'Exam mode')

    def test_no_semester_terms_in_the_lab(self):
        self.login(self.fac)
        urls = ['/', '/modules/', '/documentation/', '/about/', '/faculty/', '/faculty/batches/', f'/faculty/batches/{self.batch.pk}/', '/faculty/batches/new/']
        for url in urls:
            self.assertNotRegex(self.client.get(url).content.decode(), r'(?i)semester|\bsem\s+v', url)

    def test_pcr_module_is_catalogued_and_marks_the_fold_change(self):
        e = Experiment.objects.get(no=26)
        self.assertEqual(e.category, 'Molecular biology')
        self.assertContains(self.client.get('/modules/'), 'xh-tag-mol')
        self.login(self.st)
        r = self.client.get(e.url)
        self.assertContains(r, 'Polymerase Chain Reaction')
        self.assertContains(r, 'trueFold()')

    def test_mtt_module_is_catalogued_and_marks_the_ic50(self):
        e = Experiment.objects.get(no=27)
        self.assertEqual(e.category, 'Cell culture')
        self.assertContains(self.client.get('/modules/'), 'xh-tag-cell')
        self.login(self.st)
        r = self.client.get(e.url)
        self.assertContains(r, 'MTT Assay')
        self.assertContains(r, 'trueIC50()')

    def test_maze_modules_are_catalogued_and_mark_the_unknown(self):
        modules = self.client.get('/modules/')
        self.assertContains(modules, 'xh-tag-neuro', count=7)
        self.assertContains(modules, 'Neurobehavioural experiments')
        self.login(self.st)
        for no, title in ((28, 'Y-Maze'), (29, 'Radial Arm Maze'), (30, 'Light-Dark Box'), (31, 'Morris Water Maze'), (32, 'Barnes Maze'), (33, 'Pole Climbing'), (34, 'Forced Swim Test')):
            e = Experiment.objects.get(no=no)
            self.assertEqual(e.category, 'Neurobehavioural')
            r = self.client.get(e.url)
            self.assertContains(r, title)
            self.assertContains(r, 'unknownDrugDeduction')
            self.assertContains(r, 'mysteryKey')

    def test_modules_page_is_grouped_by_level(self):
        expected = {no: 'Research' if no in (26, 27, 35, 37) else 'Advanced' if no >= 28 and no != 30 else 'Basic' for no in range(1, 38)}
        self.assertEqual(dict(Experiment.objects.values_list('no', 'level')), expected)
        page = self.client.get('/modules/').content.decode()
        positions = [page.index(f'<section class="xh-level levelSection" data-level="{level}">') for level in ('Basic', 'Advanced', 'Research')]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(page.index('Histamine Bioassay: Matching Method'), positions[1])
        self.assertLess(page.index('Light-Dark Box'), positions[1])
        self.assertTrue(positions[1] < page.index('Barnes Maze') < positions[2])
        self.assertGreater(page.index('MTT Assay'), positions[2])
        self.assertEqual(page.count('class="catBtn"'), 2 + 3 + 7)

    def test_case_worksheet_modules_open(self):
        self.login(self.st)
        for no, title in ((35, 'Naranjo'), (36, 'IAEC'), (37, 'Good Clinical Practice')):
            e = Experiment.objects.get(no=no)
            self.assertEqual(e.category, 'Ethics and clinical')
            self.assertContains(self.client.get(e.url), title)


class AuthTests(Base):
    def test_lockout_after_failures(self):
        for _ in range(settings.LOGIN_MAX_FAILURES):
            self.client.post('/accounts/login/', {'username': 'one-bp001', 'password': 'wrong'})
        r = self.client.post('/accounts/login/', {'username': 'one-bp001', 'password': PW})
        self.assertContains(r, 'temporarily locked')
        self.assertTrue(AuditLog.objects.filter(action='account_locked').exists())
        User.objects.filter(pk=self.st.pk).update(locked_until=None)
        r = self.client.post('/accounts/login/', {'username': 'one-bp001', 'password': PW})
        self.assertEqual(r.status_code, 302)

    def test_open_redirect_blocked(self):
        r = self.client.post('/accounts/login/', {'username': 'one-bp001', 'password': PW, 'next': 'https://evil.example.com/'})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('evil', r['Location'])

    def test_consent_gate_and_record(self):
        u = mkuser('one-bp009', Role.STUDENT, self.c1, consent=False)
        self.login(u)
        r = self.client.get('/student/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/consent/', r['Location'])
        self.assertEqual(self.client.get('/privacy/').status_code, 200)  # legal pages stay readable
        r = self.client.post('/consent/?next=/student/', {'accept': 'on', 'age_ok': 'on', 'next': '/student/'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get('/student/').status_code, 200)
        self.assertTrue(ConsentRecord.objects.filter(user=u, policy_version=settings.POLICY_VERSION).exists())

    def test_policy_bump_requires_reconsent(self):
        self.login(self.st)
        with override_settings(POLICY_VERSION='2099-01-01'):
            r = self.client.get('/student/')
            self.assertIn('/consent/', r['Location'])
            r = self.client.post('/api/attempts/1/submit', data='{}', content_type='application/json')
            self.assertEqual(r.status_code, 403)

    def test_shared_demo_password_cannot_be_changed(self):
        demo = mkuser('xprismdemo', Role.STUDENT, self.c1)
        self.login(demo)
        self.assertNotContains(self.client.get('/student/'), '/accounts/password/change/')
        self.assertEqual(self.client.get('/accounts/password/change/').status_code, 302)
        r = self.client.post('/accounts/password/change/', {'new_password1': 'Changed!Pass123', 'new_password2': 'Changed!Pass123'})
        self.assertEqual(r.status_code, 302)
        demo.refresh_from_db()
        self.assertTrue(demo.check_password(PW))
        self.assertEqual(self.client.post('/accounts/password/force/', {'new_password1': 'Changed!Pass123', 'new_password2': 'Changed!Pass123'}).status_code, 302)
        demo.refresh_from_db()
        self.assertTrue(demo.check_password(PW))
        self.login(self.st)
        self.assertContains(self.client.get('/student/'), '/accounts/password/change/')

    def test_shared_demo_limits(self):
        call_command('setup_demo', stdout=io.StringIO())
        User.objects.filter(username__in=settings.SHARED_DEMO_USERNAMES).update(consent_version=settings.POLICY_VERSION)
        demo = {u.role: u for u in User.objects.filter(username__in=settings.SHARED_DEMO_USERNAMES)}
        self.assertEqual(set(demo), {Role.COLLEGE_ADMIN, Role.FACULTY, Role.LAB_ASSISTANT, Role.STUDENT})
        b = Batch.objects.get(college__code='xprism-demo')
        self.assertFalse(b.join_enabled)
        # every role's start page works, and shows the warning
        for u, url in ((demo[Role.COLLEGE_ADMIN], '/college/'), (demo[Role.FACULTY], '/faculty/'), (demo[Role.LAB_ASSISTANT], '/faculty/'), (demo[Role.STUDENT], '/student/')):
            self.login(u)
            self.assertContains(self.client.get(url), 'Shared demo:')
        # a demo college admin cannot touch people, settings or requests
        admin, fac, stu = demo[Role.COLLEGE_ADMIN], demo[Role.FACULTY], demo[Role.STUDENT]
        self.login(admin)
        for url in (f'/college/users/{fac.pk}/toggle/', f'/college/users/{fac.pk}/reset/', '/college/settings/', '/college/experiments/', '/college/requests/', '/college/users/',
                    f'/faculty/batches/{b.pk}/action/archive/', f'/faculty/batches/{b.pk}/students/{stu.pk}/reset/', f'/faculty/batches/{b.pk}/students/add/', '/faculty/batches/new/', '/me/data/'):
            self.assertEqual(self.client.post(url, {'name': 'x', 'first_name': 'x', 'roll_no': '1', 'kind': 'deletion'}).status_code, 302, url)
        fac.refresh_from_db(); stu.refresh_from_db(); b.refresh_from_db()
        self.assertTrue(fac.is_active and fac.check_password('Xprism@2026') and not fac.must_change_password)
        self.assertTrue(stu.check_password('Xprism@2026'))
        self.assertFalse(b.archived)
        self.assertEqual(Batch.objects.filter(college__code='xprism-demo').count(), 1)
        self.assertFalse(DataRequest.objects.filter(user=stu).exists())
        self.assertFalse(User.objects.filter(college__code='xprism-demo', roll_no='1').exists())
        # visitors' IP addresses stay hidden on the shared audit log
        AuditLog.objects.create(actor=stu, college=b.college, action='login', ip='203.0.113.9')
        self.assertNotContains(self.client.get('/college/audit/'), '203.0.113.9')
        # the demo works as a demo: faculty can grade, the student can submit, and repeated bad passwords lock nobody out
        self.login(fac)
        at = Attempt.objects.filter(assignment__batch=b, status=Attempt.SUBMITTED).first()
        self.client.post(f'/faculty/attempts/{at.pk}/', {'manual_marks': '7', 'feedback': 'ok'})
        at.refresh_from_db()
        self.assertEqual(at.status, Attempt.GRADED)
        self.login(stu)
        a = Assignment.objects.filter(batch=b, exam_mode=False).first()
        self.assertEqual(self.client.get(f'{a.experiment.url}?a={a.pk}').status_code, 302)  # ethics agreement first
        self.client.post('/agreement/', {'agree_ethics': 'on'})
        self.assertEqual(self.client.get(f'{a.experiment.url}?a={a.pk}').status_code, 200)
        started = Attempt.objects.get(student=stu, assignment=a, status=Attempt.STARTED)
        r = self.client.post(f'/api/attempts/{started.pk}/submit', json.dumps({'completion': True}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.client.logout()
        for _ in range(settings.LOGIN_MAX_FAILURES + 1):
            self.client.post('/accounts/login/', {'username': 'xprismdemo', 'password': 'wrong'})
        stu.refresh_from_db()
        self.assertIsNone(stu.locked_until)
        # the nightly run puts everything back and leaves other colleges alone
        batches_elsewhere = Batch.objects.exclude(college__code='xprism-demo').count()
        call_command('setup_demo', stdout=io.StringIO())
        self.assertFalse(Attempt.objects.filter(student=stu).exists())
        self.assertEqual(Batch.objects.exclude(college__code='xprism-demo').count(), batches_elsewhere)
        self.assertEqual(Batch.objects.filter(college__code='xprism-demo').count(), 1)

    def test_forced_password_change(self):
        u = mkuser('one-bp010', Role.STUDENT, self.c1, must_change_password=True)
        self.login(u)
        r = self.client.get('/student/')
        self.assertIn('/accounts/password/force/', r['Location'])
        r = self.client.post('/accounts/password/force/', {'new_password1': 'Another!Pass123', 'new_password2': 'Another!Pass123'})
        self.assertEqual(r.status_code, 302)
        u.refresh_from_db()
        self.assertFalse(u.must_change_password)
        self.assertEqual(self.client.get('/student/').status_code, 200)

    def test_signup_with_class_code(self):
        data = {'class_code': self.batch.class_code.lower(), 'first_name': 'New', 'last_name': 'Student', 'roll_no': 'BP050', 'email': '',
                'password1': 'Fresh!Pass123', 'password2': 'Fresh!Pass123', 'accept': 'on', 'age_ok': 'on'}
        r = self.client.post('/accounts/signup/', data)
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username='one-bp050')
        self.assertEqual(u.role, Role.STUDENT)
        self.assertTrue(Enrollment.objects.filter(batch=self.batch, student=u, via='class_code').exists())
        self.assertEqual(u.consent_version, settings.POLICY_VERSION)
        self.client.logout()
        r = self.client.post('/accounts/signup/', data)  # duplicate roll number
        self.assertContains(r, 'already exists')
        r = self.client.post('/accounts/signup/', {**data, 'class_code': 'NOPE1234', 'roll_no': 'BP051'})
        self.assertContains(r, 'not valid')
        r = self.client.post('/accounts/signup/', {**data, 'roll_no': 'BP052', 'accept': ''})
        self.assertFalse(User.objects.filter(username='one-bp052').exists())
        Batch.objects.filter(pk=self.batch.pk).update(join_enabled=False)
        r = self.client.post('/accounts/signup/', {**data, 'roll_no': 'BP053'})
        self.assertContains(r, 'joining is closed')


class PermissionTests(Base):
    def test_student_blocked_from_staff_areas(self):
        self.login(self.st)
        for url in ['/faculty/', f'/faculty/batches/{self.batch.pk}/', '/college/', '/college/users/', '/platform/', '/admin/']:
            r = self.client.get(url)
            self.assertIn(r.status_code, (302, 403), url)
            if url != '/admin/':
                self.assertEqual(r.status_code, 403, url)

    def test_faculty_scope(self):
        self.login(self.fac_other)
        self.assertEqual(self.client.get(f'/faculty/batches/{self.batch.pk}/').status_code, 403)
        self.assertEqual(self.client.get('/college/').status_code, 403)
        self.login(self.fac)
        self.assertEqual(self.client.get(f'/faculty/batches/{self.batch.pk}/').status_code, 200)

    def test_other_college_admin_blocked(self):
        self.login(self.ca2)
        self.assertEqual(self.client.get(f'/faculty/batches/{self.batch.pk}/').status_code, 403)
        self.assertEqual(self.client.get(f'/faculty/assignments/{self.a.pk}/').status_code, 403)
        self.assertEqual(self.client.post(f'/college/users/{self.st.pk}/toggle/').status_code, 403)

    def test_lab_assistant_limits(self):
        self.login(self.la)
        self.assertEqual(self.client.get(f'/faculty/batches/{self.batch.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'/faculty/batches/{self.batch.pk}/assignments/new/').status_code, 403)
        self.assertEqual(self.client.get(f'/faculty/batches/{self.batch.pk}/marks/?format=xlsx').status_code, 403)
        r = self.client.post(f'/faculty/batches/{self.batch.pk}/students/add/', {'first_name': 'Added', 'roll_no': 'BP077'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Enrollment.objects.filter(batch=self.batch, student__username='one-bp077').exists())
        at = Attempt.objects.create(assignment=self.a, student=self.st, status=Attempt.SUBMITTED, submitted_at=timezone.now(), auto_score=50)
        self.assertEqual(self.client.post(f'/faculty/attempts/{at.pk}/', {'manual_marks': '9', 'feedback': 'x'}).status_code, 403)

    def test_student_cannot_see_other_students_attempt(self):
        at = Attempt.objects.create(assignment=self.a, student=self.st2)
        self.login(self.st)
        r = self.client.post(f'/api/attempts/{at.pk}/submit', data='{}', content_type='application/json')
        self.assertEqual(r.status_code, 403)


class AssignmentFlowTests(Base):
    def open(self, u, a):
        self.login(u)
        return self.client.get(f'{a.experiment.url}?a={a.pk}')

    def test_full_flow_submit_grade_export(self):
        r = self.open(self.st, self.a)
        self.assertEqual(r.status_code, 200)
        c = ctx_of(r)
        self.assertEqual(c['mode'], 'assignment')
        self.assertIn('window.MCP_PROBE', r.content.decode())
        self.assertNotContains(r, '8019152501')
        at = Attempt.objects.get(pk=c['attempt'])
        payload = {'viva': {'score': 6, 'total': 7, 'items': [{'i': 0, 'q': 'pA2 is', 'chosen': 'x', 'correct': 'x', 'ok': True}]},
                   'answer': {'given': '9.02', 'truth': 9.0, 'kind': 'number', 'tol': 3.5}, 'completion': True,
                   'results': {'rows': [['pA2', '9.02']], 'text': 'ok'}, 'tables': [[['a', 'b'], ['1', '2']]]}
        r = self.client.post(c['submitUrl'], data=json.dumps(payload), content_type='application/json', HTTP_X_CSRFTOKEN=c['csrf'])
        self.assertEqual(r.status_code, 200, r.content)
        j = r.json()
        self.assertTrue(j['answer_ok'])
        self.assertAlmostEqual(j['auto_score'], round((40 * 6 / 7 + 30 + 30), 1), places=1)
        r = self.client.post(c['submitUrl'], data=json.dumps(payload), content_type='application/json')
        self.assertEqual(r.status_code, 409)
        at.refresh_from_db()
        self.assertEqual(at.status, Attempt.SUBMITTED)
        # faculty grades it
        self.login(self.fac)
        self.assertContains(self.client.get(f'/faculty/assignments/{self.a.pk}/'), 'Viva item analysis')
        r = self.client.post(f'/faculty/attempts/{at.pk}/', {'manual_marks': '8.5', 'feedback': 'Good Schild plot'})
        self.assertEqual(r.status_code, 302)
        at.refresh_from_db()
        self.assertEqual(at.final_marks, 8.5)
        self.assertEqual(at.status, Attempt.GRADED)
        r = self.client.post(f'/faculty/attempts/{at.pk}/', {'manual_marks': '11'})
        self.assertContains(r, 'Cannot exceed')
        # exports
        r = self.client.get(f'/faculty/batches/{self.batch.pk}/marks/?format=csv')
        self.assertIn('8.5', r.content.decode())
        r = self.client.get(f'/faculty/batches/{self.batch.pk}/marks/?format=xlsx')
        self.assertEqual(r['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(r.content)).active
        self.assertEqual(ws['A3'].value, 'BP001')
        # student sees grade and feedback
        self.login(self.st)
        self.assertContains(self.client.get(f'/student/assignments/{self.a.pk}/'), 'Good Schild plot')
        self.assertTrue(AuditLog.objects.filter(action='attempt_graded').exists())

    def test_wrong_choice_answer_and_attempt_limit(self):
        a = Assignment.objects.create(batch=self.batch, experiment=self.e14, due_at=timezone.now() + timezone.timedelta(days=1), max_attempts=1, created_by=self.fac)
        c = ctx_of(self.open(self.st, a))
        r = self.client.post(c['submitUrl'], data=json.dumps({'answer': {'given': '1.0', 'truth': 2.0, 'kind': 'number', 'tol': 10}, 'completion': False}), content_type='application/json')
        self.assertFalse(r.json()['answer_ok'])
        self.assertEqual(r.json()['auto_score'], 0.0)
        c = ctx_of(self.open(self.st, a))
        self.assertEqual(c['mode'], 'closed')
        self.assertIn('used all attempts', c['reason'])

    def test_exam_timeout_and_late(self):
        a = Assignment.objects.create(batch=self.batch, experiment=self.e14, due_at=timezone.now() + timezone.timedelta(days=1), exam_mode=True, time_limit_min=30, max_attempts=2, created_by=self.fac)
        c = ctx_of(self.open(self.st, a))
        self.assertTrue(c['examMode'])
        self.assertIsNotNone(c['deadline'])
        Attempt.objects.filter(pk=c['attempt']).update(started_at=timezone.now() - timezone.timedelta(minutes=45))
        c2 = ctx_of(self.open(self.st, a))       # expired attempt auto-closed; a new one starts
        self.assertNotEqual(c2['attempt'], c['attempt'])
        self.assertTrue(Attempt.objects.get(pk=c['attempt']).timed_out)
        late = Assignment.objects.create(batch=self.batch, experiment=self.e18, opens_at=timezone.now() - timezone.timedelta(days=3), due_at=timezone.now() - timezone.timedelta(days=1), allow_late=False, created_by=self.fac)
        self.assertEqual(ctx_of(self.open(self.st, late))['mode'], 'closed')
        late.allow_late = True; late.save()
        c = ctx_of(self.open(self.st, late))
        r = self.client.post(c['submitUrl'], data=json.dumps({'completion': True}), content_type='application/json')
        self.assertTrue(r.json()['late'])

    def test_student_not_in_batch_cannot_open_assignment(self):
        outsider = mkuser('one-bp099', Role.STUDENT, self.c1)
        self.login(outsider)
        self.assertEqual(self.client.get(f'{self.e18.url}?a={self.a.pk}').status_code, 404)
        self.assertEqual(ctx_of(self.client.get(self.e18.url))['mode'], 'practice')

    def test_disabled_experiment_hidden(self):
        self.c1.disabled_experiments.add(self.e14)
        self.login(self.st)
        self.assertEqual(self.client.get(self.e14.url).status_code, 403)
        self.assertNotContains(self.client.get('/modules/'), self.e14.title)

    def test_assignment_form_validation(self):
        self.login(self.fac)
        r = self.client.post(f'/faculty/batches/{self.batch.pk}/assignments/new/', {'experiment': self.e14.pk, 'opens_at': '2026-11-02T10:00', 'due_at': '2026-11-01T10:00', 'max_marks': '10', 'max_attempts': '1', 'exam_mode': 'on'})
        self.assertContains(r, 'Due date must be after')
        self.assertContains(r, 'Set a time limit')
        r = self.client.post(f'/faculty/batches/{self.batch.pk}/assignments/new/', {'experiment': self.e14.pk, 'opens_at': '2026-11-01T10:00', 'due_at': '2026-11-09T10:00', 'max_marks': '20', 'max_attempts': '1', 'exam_mode': 'on', 'time_limit_min': '40'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Assignment.objects.filter(batch=self.batch, experiment=self.e14, exam_mode=True).exists())


class EnrolmentTests(Base):
    def test_csv_upload_and_credentials_once(self):
        self.login(self.fac)
        f = io.BytesIO(b'Roll No,First Name,Last Name,Email\nBP101,Asha,Rao,asha@example.com\nBP102,Ravi,,\n,Missing,,\nBP001,Existing,,\n')
        f.name = 'list.csv'
        r = self.client.post(f'/faculty/batches/{self.batch.pk}/students/upload/', {'file': f})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='one-bp101', must_change_password=True).exists())
        r = self.client.get(f'/faculty/batches/{self.batch.pk}/students/credentials.csv')
        body = r.content.decode()
        self.assertIn('one-bp101', body)
        self.assertNotIn('one-bp001', body)  # existing account: no new password
        r = self.client.get(f'/faculty/batches/{self.batch.pk}/students/credentials.csv')
        self.assertEqual(r.status_code, 302)

    def test_xlsx_upload(self):
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.append(['roll_no', 'first_name']); ws.append(['BP201', 'Excel'])
        buf = io.BytesIO(); wb.save(buf); buf.seek(0); buf.name = 'list.xlsx'
        self.login(self.fac)
        self.client.post(f'/faculty/batches/{self.batch.pk}/students/upload/', {'file': buf})
        self.assertTrue(Enrollment.objects.filter(batch=self.batch, student__username='one-bp201').exists())

    def test_reset_password_by_faculty(self):
        self.login(self.fac)
        r = self.client.post(f'/faculty/batches/{self.batch.pk}/students/{self.st2.pk}/reset/', follow=True)
        self.assertContains(r, 'Temporary password')
        self.st2.refresh_from_db()
        self.assertTrue(self.st2.must_change_password)


class AdminTests(Base):
    def test_college_admin_creates_staff_and_toggles_experiments(self):
        self.login(self.ca)
        r = self.client.post('/college/users/', {'first_name': 'New', 'last_name': 'Prof', 'email': '', 'username': 'newprof', 'role': Role.FACULTY}, follow=True)
        self.assertContains(r, 'Temporary password')
        self.assertTrue(User.objects.filter(username='one-newprof', role=Role.FACULTY, college=self.c1).exists())
        ids = list(Experiment.objects.exclude(no=3).values_list('pk', flat=True))
        self.client.post('/college/experiments/', {'enabled': ids})
        self.assertTrue(self.c1.disabled_experiments.filter(no=3).exists())
        self.assertEqual(self.client.get('/college/audit/').status_code, 200)

    def test_platform_creates_college(self):
        self.login(self.sa)
        r = self.client.post('/platform/colleges/new/', {'name': 'Third College', 'code': 'three', 'location_text': 'Pune', 'is_active': 'on', 'admin_first_name': 'Third', 'admin_last_name': 'Admin'}, follow=True)
        self.assertContains(r, 'three-admin')
        self.assertTrue(User.objects.filter(username='three-admin', role=Role.COLLEGE_ADMIN).exists())
        self.client.post('/platform/experiments/', {f'active_{e.pk}': 'on' for e in Experiment.objects.all()})
        self.assertFalse(Experiment.objects.filter(is_demo=True).exists())

    def test_data_rights_export_and_deletion(self):
        Attempt.objects.create(assignment=self.a, student=self.st2, status=Attempt.SUBMITTED, submitted_at=timezone.now(), auto_score=70, payload={'x': 1})
        self.login(self.st2)
        r = self.client.get('/me/data/?download=1')
        data = json.loads(r.content)
        self.assertEqual(data['account']['username'], 'one-bp002')
        self.assertEqual(len(data['attempts']), 1)
        self.client.post('/me/data/', {'kind': 'deletion', 'message': 'Leaving college'})
        req = DataRequest.objects.get(kind='deletion')
        self.login(self.ca2)
        self.assertEqual(self.client.post('/college/requests/', {'id': req.pk, 'decision': 'approve'}).status_code, 404)
        self.login(self.ca)
        self.client.post('/college/requests/', {'id': req.pk, 'decision': 'approve'})
        u = User.objects.get(pk=self.st2.pk)
        self.assertTrue(u.anonymised)
        self.assertFalse(u.is_active)
        self.assertEqual(u.roll_no, '')
        self.assertEqual(Attempt.objects.get(student=u).payload, {})
        self.assertEqual(Attempt.objects.get(student=u).auto_score, 70)  # de-identified marks retained


class PageRenderTests(Base):
    """Every role's pages render without template errors."""
    def test_all_role_pages_render(self):
        Attempt.objects.create(assignment=self.a, student=self.st, status=Attempt.SUBMITTED, submitted_at=timezone.now(), auto_score=60,
                               payload={'results': {'rows': [['a', 'b']], 'text': 't'}, 'tables': [[['h1', 'h2'], ['1', '2']]], 'viva': {'items': [{'i': 0, 'q': 'Q', 'chosen': 'A', 'correct': 'A', 'ok': True}]}})
        at = Attempt.objects.first()
        pages = {
            self.st: ['/', '/student/', f'/student/assignments/{self.a.pk}/', '/me/data/', '/accounts/password/change/', self.e18.url],
            self.fac: ['/faculty/', '/faculty/batches/', '/faculty/batches/new/', f'/faculty/batches/{self.batch.pk}/', f'/faculty/batches/{self.batch.pk}/edit/', f'/faculty/batches/{self.batch.pk}/marks/', f'/faculty/batches/{self.batch.pk}/assignments/new/', f'/faculty/assignments/{self.a.pk}/', f'/faculty/assignments/{self.a.pk}/edit/', f'/faculty/attempts/{at.pk}/', self.e18.url + '?exam=1'],
            self.la: ['/faculty/', f'/faculty/batches/{self.batch.pk}/', f'/faculty/attempts/{at.pk}/'],
            self.ca: ['/college/', '/college/users/', '/college/users/?role=students&q=bp', '/college/experiments/', '/college/settings/', '/college/audit/', '/college/requests/', '/faculty/batches/'],
            self.sa: ['/platform/', '/platform/trials/', '/subscribe/', '/ethics/', '/platform/colleges/', '/platform/colleges/new/', f'/platform/colleges/{self.c1.pk}/', '/platform/experiments/', '/college/requests/', '/college/audit/', '/admin/', '/admin/lab/user/'],
        }
        for u, urls in pages.items():
            self.login(u)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 200, f'{u.username} {url}')
        self.assertEqual(self.client.get('/home/').status_code, 302)


class TrialTests(Base):
    def signup(self, email='trial@example.com'):
        return self.client.post('/accounts/trial/', {'first_name': 'Tara', 'last_name': 'Trial', 'email': email, 'institution': 'Some College',
                                                     'occupation': 'student', 'password1': 'Trial!Pass123', 'password2': 'Trial!Pass123', 'accept': 'on', 'age_ok': 'on'})

    def test_trial_journey_one_visit_per_module(self):
        r = self.signup()
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username='trial@example.com')
        self.assertTrue(u.is_trial_account)
        self.assertFalse(u.has_full_access)
        # pop-up shown; experiments blocked until agreement
        r = self.client.get('/')
        self.assertContains(r, 'FREE TRIAL RULES')
        self.assertContains(r, 'CCSEA')
        self.assertContains(r, 'PETA India')
        e1, e2 = Experiment.objects.get(no=1), Experiment.objects.get(no=2)
        r = self.client.get(e1.url)
        self.assertIn('agree=1', r['Location'])
        self.client.post('/agreement/', {'agree_ethics': 'on'})        # trial box missing: refused
        u.refresh_from_db(); self.assertEqual(u.ethics_version, '')
        self.client.post('/agreement/', {'agree_ethics': 'on', 'agree_trial': 'on', 'next': '/'})
        u.refresh_from_db(); self.assertEqual(u.ethics_version, settings.ETHICS_VERSION)
        self.assertTrue(ConsentRecord.objects.filter(user=u, policy_version=f'ethics-{settings.ETHICS_VERSION}').exists())
        self.assertNotContains(self.client.get('/'), 'FREE TRIAL RULES')
        # first visit + reload allowed
        r = self.client.get(e1.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ctx_of(r)['mode'], 'trial')
        self.assertEqual(self.client.get(e1.url).status_code, 200)
        # back to the lab index ends the visit
        r = self.client.get('/modules/')
        self.assertContains(r, 'Subscription only')
        r = self.client.get(e1.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/subscribe/?exp=', r['Location'])
        r = self.client.get(r['Location'])
        self.assertEqual(r.status_code, 402)
        self.assertContains(r, 'You have already explored', status_code=402)
        # opening another module ends the previous one
        self.assertEqual(self.client.get(e2.url).status_code, 200)
        e3 = Experiment.objects.get(no=3)
        self.assertEqual(self.client.get(e3.url).status_code, 200)
        self.assertEqual(TrialVisit.objects.get(user=u, experiment=e2).consumed_by, 'other_module')
        # expiry
        TrialVisit.objects.filter(user=u, experiment=e3).update(started_at=timezone.now() - timezone.timedelta(hours=settings.TRIAL_VISIT_MAX_HOURS + 1))
        self.assertEqual(self.client.get(e3.url).status_code, 302)
        # going to the home page ends an open visit
        e5 = Experiment.objects.get(no=5)
        self.assertEqual(self.client.get(e5.url).status_code, 200)
        self.client.get('/')
        self.assertEqual(TrialVisit.objects.get(user=u, experiment=e5).consumed_by, 'index')
        # sign-out ends an open visit
        e4 = Experiment.objects.get(no=4)
        self.client.get(e4.url)
        self.client.post('/accounts/logout/')
        self.assertEqual(TrialVisit.objects.get(user=u, experiment=e4).consumed_by, 'logout')
        # cannot submit assignments; students' nav is trial nav
        self.assertEqual(TrialVisit.objects.filter(user=u, consumed_at__isnull=False).count(), 5)

    def test_duplicate_trial_email_refused(self):
        self.signup('dup@example.com')
        self.client.logout()
        r = self.signup('DUP@example.com')
        self.assertContains(r, 'already exists')

    def test_full_access_users_unlimited_and_need_only_ethics(self):
        u = mkuser('one-bp050', Role.STUDENT, self.c1, ethics=False)
        self.login(u)
        r = self.client.get('/')
        self.assertContains(r, 'ETHICAL USE AGREEMENT')
        self.assertNotContains(r, 'FREE TRIAL RULES')
        self.client.post('/agreement/', {'agree_ethics': 'on'})
        e1 = Experiment.objects.get(no=1)
        for _ in range(3):
            self.assertEqual(self.client.get(e1.url).status_code, 200)
            self.client.get('/')
        self.assertFalse(TrialVisit.objects.filter(user=u).exists())

    def test_lapsed_college_falls_back_to_trial_and_assignment_ignored(self):
        College.objects.filter(pk=self.c1.pk).update(subscription_until=timezone.localdate() - timezone.timedelta(days=1))
        self.login(self.st)
        r = self.client.get(f'{self.e18.url}?a={self.a.pk}')
        self.assertEqual(ctx_of(r)['mode'], 'trial')
        self.assertFalse(Attempt.objects.filter(student=self.st).exists())
        self.client.get('/student/')
        self.assertEqual(self.client.get(self.e18.url).status_code, 302)
        self.login(self.ca)
        self.assertContains(self.client.get('/college/'), 'lapsed')

    def test_platform_grants_individual_subscription_and_resets(self):
        self.signup('buyer@example.com')
        u = User.objects.get(username='buyer@example.com')
        TrialVisit.objects.create(user=u, experiment=self.e18, consumed_at=timezone.now())
        self.login(self.sa)
        self.assertContains(self.client.get('/platform/trials/'), 'buyer@example.com')
        until = (timezone.localdate() + timezone.timedelta(days=30)).isoformat()
        self.client.post('/platform/trials/', {'user': u.pk, 'action': 'grant', 'until': until})
        u.refresh_from_db()
        self.assertTrue(u.has_full_access)
        self.client.post('/platform/trials/', {'user': u.pk, 'action': 'reset'})
        self.assertFalse(TrialVisit.objects.filter(user=u).exists())
        self.client.post('/platform/trials/', {'user': u.pk, 'action': 'revoke'})
        u.refresh_from_db()
        self.assertFalse(u.has_full_access)


class SignupEmailTests(Base):
    """Verification + welcome e-mails go out automatically after self sign-up."""
    TRIAL = {'first_name': 'Tara', 'last_name': 'Trial', 'email': 'tara@example.com', 'institution': 'Some College',
             'occupation': 'student', 'password1': 'Trial!Pass123', 'password2': 'Trial!Pass123', 'accept': 'on', 'age_ok': 'on'}

    def class_data(self, **kw):
        return {'class_code': self.batch.class_code, 'first_name': 'New', 'last_name': 'Student', 'roll_no': 'BP070', 'email': 'new@example.com',
                'password1': 'Fresh!Pass123', 'password2': 'Fresh!Pass123', 'accept': 'on', 'age_ok': 'on', **kw}

    def post(self, url, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, data)

    @staticmethod
    def link_in(msg):
        return re.search(r'https?://[^/\s]+(/accounts/verify/[^\s]+/)', msg.body).group(1)

    def test_trial_signup_sends_verification_and_welcome(self):
        from django.core import mail
        r = self.post('/accounts/trial/', self.TRIAL)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        verify, welcome = mail.outbox
        self.assertEqual(verify.to, ['tara@example.com'])
        self.assertIn('Verify', verify.subject)
        self.assertIn('Welcome', welcome.subject)
        self.assertIn('Free trial', welcome.body)
        self.assertEqual(verify.alternatives[0][1], 'text/html')
        u = User.objects.get(username='tara@example.com')
        self.assertFalse(u.email_verified)
        self.assertContains(self.client.get('/student/', follow=True), 'Resend verification e-mail')
        # the link verifies, even when signed out, and only once
        self.client.logout()
        link = self.link_in(verify)
        r = self.client.get(link)
        self.assertContains(r, 'E-mail verified')
        u.refresh_from_db()
        self.assertTrue(u.email_verified)
        self.assertIsNotNone(u.email_verified_at)
        self.assertTrue(AuditLog.objects.filter(action='email_verified', target=u.username).exists())
        self.assertContains(self.client.get(link), 'Already verified')

    def test_class_code_signup_welcome_includes_username_and_class(self):
        from django.core import mail
        self.post('/accounts/signup/', self.class_data())
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('one-bp070', mail.outbox[1].body)
        self.assertIn(self.batch.name, mail.outbox[1].body)
        self.assertNotIn('Free trial', mail.outbox[1].body)

    def test_class_code_signup_without_email_sends_nothing(self):
        from django.core import mail
        r = self.post('/accounts/signup/', self.class_data(email='', roll_no='BP071'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotContains(self.client.get('/student/'), 'Resend verification e-mail')

    def test_bad_or_tampered_link_refused(self):
        from django.core import mail
        self.post('/accounts/trial/', self.TRIAL)
        link = self.link_in(mail.outbox[0])
        self.assertEqual(self.client.get(link[:-3] + 'xx/').status_code, 400)
        self.assertEqual(self.client.get('/accounts/verify/zzz/abc-def/').status_code, 400)
        # changing the address invalidates the old link
        User.objects.filter(username='tara@example.com').update(email='other@example.com')
        self.assertEqual(self.client.get(link).status_code, 400)
        self.assertFalse(User.objects.get(username='tara@example.com').email_verified)

    def test_resend_is_throttled(self):
        from django.core import mail
        from django.core.cache import cache
        cache.clear()
        self.post('/accounts/trial/', self.TRIAL)
        mail.outbox.clear()
        self.client.post('/accounts/verify/resend/', {'next': '/student/'})
        self.client.post('/accounts/verify/resend/')
        self.assertEqual(len(mail.outbox), 1)
        self.client.get(self.link_in(mail.outbox[0]))
        cache.clear()
        self.client.post('/accounts/verify/resend/')
        self.assertEqual(len(mail.outbox), 1)          # already verified: nothing more sent

    def test_mail_failure_does_not_break_signup(self):
        from unittest import mock
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=OSError('smtp down')), self.assertLogs('lab.emails', 'ERROR'):
            r = self.post('/accounts/trial/', self.TRIAL)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='tara@example.com').exists())


@override_settings(SUBSCRIPTION_CONTACT='owner@example.com')
class FreeYearTests(Base):
    FORM = {'kind': 'individual', 'name': 'Asha Rao', 'email': 'Asha@Example.com', 'institution': 'Rao College', 'occupation': 'faculty', 'consent': 'on'}

    def setUp(self):
        cache.clear()

    def apply(self, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/free-year/apply', {**self.FORM, **extra})

    def decide(self, app, decision='approve', **extra):
        self.login(self.sa)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/platform/free-year/', {'id': app.pk, 'decision': decision, **extra}, follow=True)

    def test_popup_shown_to_visitors_and_trial_users_only(self):
        self.assertContains(self.client.get('/'), 'id="freeYearModal"')
        self.assertNotContains(self.client.get('/accounts/login/'), 'id="freeYearModal"')
        trial = mkuser('t@example.com', Role.STUDENT, is_trial_account=True, email='t@example.com')
        self.login(trial)
        self.assertContains(self.client.get('/modules/'), 'id="freeYearModal"')
        self.assertContains(self.client.get('/subscribe/'), 'data-free-year-open')
        FreeYearApplication.objects.create(name='T', email=trial.email, institution='X', user=trial)
        self.assertNotContains(self.client.get('/modules/'), 'id="freeYearModal"')
        self.login(self.st)     # a student of a subscribed college already has access
        self.assertNotContains(self.client.get('/modules/'), 'id="freeYearModal"')

    def test_application_reaches_super_admin(self):
        r = self.apply()
        self.assertEqual(r.json()['ok'], True)
        app = FreeYearApplication.objects.get()
        self.assertEqual((app.email, app.status), ('asha@example.com', FreeYearApplication.PENDING))
        self.assertEqual([m.to for m in mail.outbox], [['owner@example.com'], ['asha@example.com']])
        self.assertIn('Rao College', mail.outbox[0].body)
        self.assertIn('/platform/free-year/', mail.outbox[0].body)
        self.login(self.sa)
        self.assertContains(self.client.get('/platform/free-year/'), 'Asha Rao')
        self.assertEqual(self.client.get('/platform/').context['stats']['free_year'], 1)

    def test_invalid_form_returns_field_errors(self):
        r = self.apply(email='nope', consent='', phone='abc')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['errors']), {'email', 'consent', 'phone'})
        self.assertFalse(FreeYearApplication.objects.exists())

    def test_repeat_application_and_bot_are_answered_but_not_saved(self):
        self.apply()
        mail.outbox.clear()
        self.assertEqual(self.apply(email='ASHA@example.com').json()['ok'], True)
        self.assertEqual(self.apply(email='bot@example.com', website='http://spam').json()['ok'], True)
        self.assertEqual(FreeYearApplication.objects.count(), 1)
        self.assertEqual(mail.outbox, [])

    def test_declined_applicant_may_apply_again(self):
        self.apply()
        self.decide(FreeYearApplication.objects.get(), 'decline', note='Could not verify')
        self.client.logout()
        self.apply()
        self.assertEqual(FreeYearApplication.objects.filter(status=FreeYearApplication.PENDING).count(), 1)

    def test_rate_limit_per_network(self):
        for i in range(5):
            self.assertEqual(self.apply(email=f'a{i}@example.com').status_code, 200)
        self.assertEqual(self.apply(email='a6@example.com').status_code, 429)
        self.assertEqual(self.client.post('/api/free-year/apply', {**self.FORM, 'email': 'a7@example.com'}, HTTP_X_REAL_IP='203.0.113.9').status_code, 200)
        self.assertEqual(FreeYearApplication.objects.count(), 6)

    def test_only_super_admin_can_review(self):
        self.assertEqual(self.client.get('/platform/free-year/').status_code, 302)
        for u in (self.ca, self.fac, self.st):
            self.login(u)
            self.assertEqual(self.client.get('/platform/free-year/').status_code, 403)
        self.client.logout()
        self.apply()
        app = FreeYearApplication.objects.get()
        self.login(self.ca)
        self.assertEqual(self.client.post('/platform/free-year/', {'id': app.pk, 'decision': 'approve'}).status_code, 403)
        app.refresh_from_db()
        self.assertEqual(app.status, FreeYearApplication.PENDING)

    def test_approve_individual_creates_account_with_a_year_and_password_link(self):
        self.apply()
        mail.outbox.clear()
        app = FreeYearApplication.objects.get()
        self.decide(app, 'approve')
        u = User.objects.get(username='asha@example.com')
        year = one_year_after(timezone.localdate())
        self.assertEqual((u.subscribed_until, u.is_trial_account, u.first_name, u.last_name), (year, True, 'Asha', 'Rao'))
        self.assertTrue(u.has_full_access)
        app.refresh_from_db()
        self.assertEqual((app.status, app.user, app.awarded_until, app.reviewed_by), (FreeYearApplication.APPROVED, u, year, self.sa))
        self.assertEqual(AuditLog.objects.filter(action='free_year_approve').count(), 1)
        link = re.search(r'http://testserver(/accounts/password/reset/\S+)', mail.outbox[0].body).group(1)
        self.client.logout()
        self.assertContains(self.client.get(link, follow=True), 'new_password1')

    def test_approve_extends_existing_account_from_its_end_date(self):
        end = timezone.localdate() + timezone.timedelta(days=30)
        t = mkuser('t@example.com', Role.STUDENT, is_trial_account=True, email='t@example.com', subscribed_until=end)
        self.apply(email='T@example.com')
        mail.outbox.clear()
        self.decide(FreeYearApplication.objects.get())
        t.refresh_from_db()
        self.assertEqual(t.subscribed_until, one_year_after(end))
        self.assertEqual(User.objects.filter(email='t@example.com').count(), 1)
        self.assertNotIn('/accounts/password/reset/', mail.outbox[0].body)

    def test_approve_college_creates_college_and_admin(self):
        self.apply(kind='college', institution='Rao College of Pharmacy')
        self.decide(FreeYearApplication.objects.get(), college='new')
        c = College.objects.get(name='Rao College of Pharmacy')
        admin = User.objects.get(college=c, role=Role.COLLEGE_ADMIN)
        self.assertEqual(c.subscription_until, one_year_after(timezone.localdate()))
        self.assertTrue(c.is_subscribed)
        self.assertEqual((admin.username, admin.email), (f'{c.code}-admin', 'asha@example.com'))

    def test_approve_college_renews_a_lapsed_college_without_new_admin(self):
        College.objects.filter(pk=self.c2.pk).update(subscription_until=timezone.localdate() - timezone.timedelta(days=9))
        n = User.objects.count()
        self.apply(kind='college', institution='College Two')
        self.decide(FreeYearApplication.objects.get(), college=self.c2.pk)
        self.c2.refresh_from_db()
        self.assertEqual(self.c2.subscription_until, one_year_after(timezone.localdate()))
        self.assertEqual(User.objects.count(), n)

    def test_approve_keeps_a_college_with_no_end_date(self):
        self.apply(kind='college', institution='College Two')
        app = FreeYearApplication.objects.get()
        self.decide(app, college=self.c2.pk)
        self.c2.refresh_from_db()
        app.refresh_from_db()
        self.assertIsNone(self.c2.subscription_until)
        self.assertEqual(app.awarded_college, self.c2)

    def test_decline_tells_applicant_and_gives_no_access(self):
        self.apply()
        mail.outbox.clear()
        app = FreeYearApplication.objects.get()
        self.decide(app, 'decline', note='Could not verify')
        app.refresh_from_db()
        self.assertEqual(app.status, FreeYearApplication.REJECTED)
        self.assertFalse(User.objects.filter(username='asha@example.com').exists())
        self.assertIn('Could not verify', mail.outbox[0].body)

    def test_decided_application_cannot_be_awarded_twice(self):
        self.apply()
        app = FreeYearApplication.objects.get()
        self.decide(app)
        first = User.objects.get(username='asha@example.com').subscribed_until
        self.assertContains(self.decide(app), 'already been decided')
        self.assertEqual(User.objects.get(username='asha@example.com').subscribed_until, first)

    def test_account_with_full_access_and_shared_demo_cannot_apply(self):
        self.login(self.st)
        self.assertEqual(self.apply().status_code, 400)
        demo = mkuser('xprismdemo', Role.STUDENT)
        self.login(demo)
        self.assertEqual(self.apply().status_code, 403)
        self.assertFalse(FreeYearApplication.objects.exists())

    def test_signed_in_applicant_cannot_apply_as_someone_else(self):
        t = mkuser('t@example.com', Role.STUDENT, is_trial_account=True, email='t@example.com')
        self.login(t)
        self.apply(email='other@example.com')
        app = FreeYearApplication.objects.get()
        self.assertEqual((app.user, app.email), (t, 't@example.com'))

    def test_deleting_an_account_erases_its_applications(self):
        t = mkuser('t@example.com', Role.STUDENT, is_trial_account=True, email='t@example.com')
        app = FreeYearApplication.objects.create(name='T', email='t@example.com', phone='9999999999', institution='X')
        anonymise_user(t)
        app.refresh_from_db()
        self.assertEqual((app.email, app.phone, app.status), ('', '', FreeYearApplication.REJECTED))

    def test_emails_carry_the_logo_and_site_colours(self):
        self.apply()
        msg = mail.outbox[0].message()
        self.assertEqual(msg.get_content_type(), 'multipart/related')
        logo = [p for p in msg.walk() if p.get_content_type() == 'image/png'][0]
        self.assertEqual(logo['Content-ID'], '<xprism-logo>')
        html = [p for p in msg.walk() if p.get_content_type() == 'text/html'][0].get_payload(decode=True).decode()
        self.assertIn('src="cid:xprism-logo"', html)
        self.assertIn('#7e13b5', html)
        self.assertNotIn('#0d9488', html)

    def test_year_end_on_leap_day(self):
        self.assertEqual(one_year_after(datetime.date(2028, 2, 29)), datetime.date(2029, 2, 28))


class FreeYearInvitationTests(Base):
    URL = '/platform/free-year/invite/'

    def setUp(self):
        self.login(self.sa)

    def invite(self, addresses, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.URL, {'addresses': addresses, **extra}, follow=True)

    def test_only_super_admin_can_invite(self):
        self.login(self.ca)
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.client.post(self.URL, {'addresses': 'a@example.com'}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.URL).status_code, 302)
        self.assertFalse(FreeYearInvitation.objects.exists())

    def test_each_address_gets_its_own_email_with_apply_and_opt_out_links(self):
        self.invite('Principal@College.edu, hod@college.edu; dean@college.edu\nhod@college.edu', note='We met at <the> conference')
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['dean@college.edu', 'hod@college.edu', 'principal@college.edu'])
        self.assertTrue(all(len(m.to) == 1 and not m.cc and not m.bcc for m in mail.outbox))
        inv = FreeYearInvitation.objects.get(email='hod@college.edu')
        self.assertEqual((inv.status, inv.invited_by), (FreeYearInvitation.SENT, self.sa))
        self.assertIsNotNone(inv.sent_at)
        msg = next(m for m in mail.outbox if m.to == ['hod@college.edu'])
        self.assertIn('http://testserver/?apply=1', msg.body)
        self.assertIn(f'/invitation/opt-out/{inv.token}/', msg.body)
        self.assertIn(inv.token, msg.extra_headers['List-Unsubscribe'])
        self.assertIn('We met at <the> conference', msg.body)
        self.assertIn('We met at &lt;the&gt; conference', msg.alternatives[0][0])

    def test_invitation_addresses_management_and_lists_about_modules_and_company(self):
        Experiment.objects.filter(no=25).update(is_active=False)
        self.invite('a@college.edu')
        msg = mail.outbox[0]
        html = msg.alternatives[0][0]
        for text in ('The Management and Administration', 'About XPRISM', 'Modules in XPRISM (36)', 'Isolated tissue experiments', 'Aaron Innovations', 'Kolkata, India', 'developed by Dr. Vara Prasad Saka', self.e14.title):
            self.assertIn(text, html)
        self.assertNotIn('New Delhi', html)
        self.assertNotIn('Castor Oil', html)
        self.assertIn(f'{self.e18.no}. {self.e18.title}', msg.body)
        self.assertIn('Kolkata, India', msg.body)
        self.assertNotIn('Castor Oil', msg.body)

    def test_invalid_and_already_contacted_addresses_are_skipped(self):
        FreeYearInvitation.objects.create(email='old@college.edu', status=FreeYearInvitation.SENT)
        FreeYearApplication.objects.create(name='A', email='applied@college.edu', institution='X')
        r = self.invite('old@college.edu applied@college.edu not-an-email new@college.edu')
        self.assertEqual([m.to for m in mail.outbox], [['new@college.edu']])
        self.assertContains(r, 'not-an-email')
        self.assertContains(r, 'Skipped 2')

    def test_nothing_valid_keeps_the_pasted_text(self):
        r = self.invite('not-an-email')
        self.assertEqual(mail.outbox, [])
        self.assertContains(r, '>not-an-email</textarea>')

    @override_settings(FREE_YEAR_INVITES_PER_DAY=2)
    def test_daily_limit(self):
        FreeYearInvitation.objects.create(email='today@college.edu', status=FreeYearInvitation.SENT, sent_at=timezone.now())
        FreeYearInvitation.objects.create(email='lastweek@college.edu', status=FreeYearInvitation.SENT, sent_at=timezone.now() - timezone.timedelta(days=7))
        r = self.invite('a@college.edu b@college.edu')
        self.assertEqual([m.to for m in mail.outbox], [['a@college.edu']])
        self.assertContains(r, 'b@college.edu')
        self.assertFalse(FreeYearInvitation.objects.filter(email='b@college.edu').exists())

    def test_failed_send_is_recorded_and_can_be_retried(self):
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=OSError('no route')), self.assertLogs('lab.emails', 'ERROR'):
            self.invite('a@college.edu')
        inv = FreeYearInvitation.objects.get()
        self.assertEqual(inv.status, FreeYearInvitation.FAILED)
        self.assertIsNone(inv.sent_at)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.URL, {'retry': inv.pk})
        inv.refresh_from_db()
        self.assertEqual(inv.status, FreeYearInvitation.SENT)
        self.assertEqual([m.to for m in mail.outbox], [['a@college.edu']])

    @override_settings(DEBUG=False, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_refuses_to_send_when_email_is_not_set_up(self):
        self.assertContains(self.client.get(self.URL), 'E-mail is not set up')
        self.client.post(self.URL, {'addresses': 'a@college.edu'})
        self.assertFalse(FreeYearInvitation.objects.exists())

    def test_opt_out_needs_a_click_and_stops_further_invitations(self):
        inv = FreeYearInvitation.objects.create(email='a@college.edu', status=FreeYearInvitation.FAILED)
        self.client.logout()
        url = f'/invitation/opt-out/{inv.token}/'
        self.assertContains(self.client.get(url), 'Stop invitation e-mails?')
        inv.refresh_from_db()
        self.assertIsNone(inv.opted_out_at)
        self.assertContains(self.client.post(url), 'You have opted out')
        inv.refresh_from_db()
        self.assertIsNotNone(inv.opted_out_at)
        self.assertEqual(self.client.get('/invitation/opt-out/wrong/').status_code, 404)
        self.login(self.sa)
        self.invite('a@college.edu')
        self.assertEqual(mail.outbox, [])
        self.assertContains(self.client.post(self.URL, {'retry': inv.pk}, follow=True), 'cannot be retried')
        self.assertEqual(mail.outbox, [])

    def test_invitation_still_sending_cannot_be_sent_twice(self):
        inv = FreeYearInvitation.objects.create(email='a@college.edu')
        self.assertNotContains(self.client.get(self.URL), 'Try again')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.URL, {'retry': inv.pk})
        self.assertEqual(mail.outbox, [])
        FreeYearInvitation.objects.filter(pk=inv.pk).update(created_at=timezone.now() - timezone.timedelta(hours=2))
        self.assertContains(self.client.get(self.URL), 'Try again')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.URL, {'retry': inv.pk})
        self.assertEqual([m.to for m in mail.outbox], [['a@college.edu']])

    def test_response_is_shown_to_super_admin(self):
        FreeYearInvitation.objects.create(email='a@college.edu', status=FreeYearInvitation.SENT, sent_at=timezone.now())
        FreeYearApplication.objects.create(name='A', email='a@college.edu', institution='X')
        self.assertContains(self.client.get(self.URL), 'Applied: Pending')

    def test_invitation_link_opens_the_popup(self):
        self.client.logout()
        self.assertContains(self.client.get('/?apply=1'), "get('apply') === '1'")
