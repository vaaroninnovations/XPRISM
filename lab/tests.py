import datetime
import io
import json
import os
import re
import tempfile
from email.utils import format_datetime
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from . import mailbox
from .free_year import one_month_after
from .models import Assignment, Attempt, AuditLog, Batch, College, ConsentRecord, ContactRequest, DataRequest, Enrollment, Experiment, ExperimentFeedback, FreeYearApplication, MailMessage, FreeYearInvitation, Role, TrialVisit, User
from .storage import VersionedStaticFilesStorage
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
        self.assertContains(self.client.get('/'), '© 2026 Aaron Innovations</p>')
        self.assertNotContains(self.client.get('/'), 'Created by')          # the creator is named on the About page, not in the footer
        self.assertNotContains(self.client.get('/'), 'MyCAL')

    def test_home_modules_and_documentation_are_public(self):
        home = self.client.get('/')
        for text in ['Replacement', 'Reduction', 'Refinement', 'Read about ethical use of animals', '/accounts/trial/', '/accounts/signup/', '/accounts/login/', '/modules/', '/documentation/']:
            self.assertContains(home, text)
        self.assertContains(home, 'class="expCard', count=6)
        self.assertContains(self.client.get('/modules/'), 'class="expCard', count=43)
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
        expected = {no: 'Research' if no in (26, 27, 35, 37, 39, 40, 43) else 'Advanced' if 28 <= no <= 36 and no != 30 else 'Basic' for no in range(1, 44)}
        self.assertEqual(dict(Experiment.objects.values_list('no', 'level')), expected)
        page = self.client.get('/modules/').content.decode()
        positions = [page.index(f'<section class="xh-level levelSection" data-level="{level}">') for level in ('Basic', 'Advanced', 'Research')]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(page.index('Histamine Bioassay: Matching Method'), positions[1])
        self.assertLess(page.index('Light-Dark Box'), positions[1])
        self.assertTrue(positions[1] < page.index('Barnes Maze') < positions[2])
        self.assertGreater(page.index('MTT Assay'), positions[2])
        self.assertEqual(page.count('class="catBtn"'), 2 + 3 + 10)

    def test_case_worksheet_modules_open(self):
        self.login(self.st)
        for no, title in ((35, 'Naranjo'), (36, 'IAEC'), (37, 'Good Clinical Practice')):
            e = Experiment.objects.get(no=no)
            self.assertEqual(e.category, 'Ethics and clinical')
            self.assertContains(self.client.get(e.url), title)

    def test_assay_modules_open(self):
        self.login(self.st)
        for no, title in ((38, 'Creatinine'), (39, 'Sandwich ELISA'), (40, 'Reduced Glutathione')):
            e = Experiment.objects.get(no=no)
            self.assertEqual(e.category, 'Biochemical assays')
            self.assertContains(self.client.get(e.url), title)

    def test_foundation_and_docking_modules_open(self):
        self.login(self.st)
        for no, title, cat in ((41, 'Rota-rod', 'Laboratory foundations'), (42, 'Tyrode', 'Laboratory foundations'), (43, 'RMSD', 'In silico')):
            e = Experiment.objects.get(no=no)
            self.assertEqual(e.category, cat)
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


class FeedbackTests(Base):
    """The report a student reads after submitting, and the rating they give the experiment."""
    VIVA = {'score': 1, 'total': 2, 'answered': 2, 'items': [{'i': 0, 'q': 'pA2 is', 'chosen': 'x', 'correct': 'x', 'ok': True},
                                                              {'i': 1, 'q': 'A Schild slope of 1 means', 'chosen': 'non-competitive', 'correct': 'competitive antagonism', 'ok': False}]}

    def submit(self, a=None, **payload):
        a = a or self.a
        self.login(self.st)
        c = ctx_of(self.client.get(f'{a.experiment.url}?a={a.pk}'))
        r = self.client.post(c['submitUrl'], data=json.dumps(payload), content_type='application/json')
        return c, r.json()

    def rate(self, exp, **data):
        return self.client.post(f'/api/experiments/{exp.slug}/feedback', data=json.dumps(data), content_type='application/json')

    def test_report_says_what_each_part_earned_and_what_to_revise(self):
        c, j = self.submit(viva=self.VIVA, answer={'given': '7.1', 'truth': 9.0, 'kind': 'number', 'tol': 3.5}, completion=True)
        rep = j['report']
        self.assertEqual([p['key'] for p in rep['parts']], ['viva', 'answer', 'observations'])
        self.assertEqual([p['state'] for p in rep['parts']], ['partial', 'missed', 'good'])
        self.assertEqual(sum(p['earned'] for p in rep['parts']), round(j['auto_score']))
        self.assertEqual(rep['revise'], [{'q': 'A Schild slope of 1 means', 'chosen': 'non-competitive', 'correct': 'competitive antagonism'}])
        self.assertIn('outside the accepted range', rep['parts'][1]['advice'])
        self.assertNotIn('9.0', json.dumps(rep))                     # the true value of the unknown is never sent back
        self.assertEqual(rep['attempts_left'], self.a.max_attempts - 1)
        self.assertTrue(c['canRate'])
        page = self.client.get(f'/student/assignments/{self.a.pk}/')
        self.assertContains(page, 'Viva questions to revise (1)')
        self.assertContains(page, 'competitive antagonism')
        self.assertContains(page, 'id="rateBox"')

    def test_exam_mode_keeps_the_viva_answers_hidden(self):
        self.a.exam_mode, self.a.time_limit_min = True, 30
        self.a.save()
        c, j = self.submit(viva=self.VIVA, completion=True)
        self.assertEqual(j['report']['revise'], [])
        self.assertIn('answers stay hidden', j['report']['parts'][0]['advice'])
        self.assertNotContains(self.client.get(f'/student/assignments/{self.a.pk}/'), 'competitive antagonism')

    def test_student_rates_a_submitted_attempt_once(self):
        c, j = self.submit(viva=self.VIVA, completion=True)
        at = j['report']['attempt']
        self.assertEqual(self.rate(self.e18, rating=0, attempt=at).status_code, 400)
        self.assertEqual(self.rate(self.e18, rating='abc').status_code, 400)
        self.assertEqual(self.rate(self.e18, rating=4, difficulty='hard', comment=' Schild plot needs a worked example ', attempt=at).status_code, 200)
        self.assertEqual(self.rate(self.e18, rating=5, difficulty='nonsense', attempt=at).status_code, 200)       # sending again replaces the rating
        f = ExperimentFeedback.objects.get()
        self.assertEqual((f.rating, f.difficulty, f.context, f.college, f.user), (5, '', 'assignment', self.c1, self.st))
        self.assertContains(self.client.get(f'/student/assignments/{self.a.pk}/'), 'You rated this experiment')
        self.assertTrue(AuditLog.objects.filter(action='experiment_feedback').exists())

    def test_rating_needs_a_submitted_attempt_of_your_own(self):
        self.login(self.st)
        c = ctx_of(self.client.get(f'{self.a.experiment.url}?a={self.a.pk}'))
        self.assertEqual(self.rate(self.e18, rating=4, attempt=c['attempt']).status_code, 400)        # still in progress
        self.client.post(c['submitUrl'], data='{}', content_type='application/json')
        self.assertEqual(self.rate(self.e14, rating=4, attempt=c['attempt']).status_code, 400)        # another experiment
        self.login(self.st2)
        self.assertEqual(self.rate(self.e18, rating=4, attempt=c['attempt']).status_code, 400)        # another student's attempt
        self.login(self.fac)
        self.assertEqual(self.rate(self.e18, rating=4).status_code, 403)
        self.client.logout()
        self.assertEqual(self.rate(self.e18, rating=4).status_code, 401)
        self.assertFalse(ExperimentFeedback.objects.exists())

    def test_practice_rating_is_one_per_experiment(self):
        self.login(self.st)
        self.assertTrue(ctx_of(self.client.get(self.e14.url))['feedbackUrl'].endswith(f'/api/experiments/{self.e14.slug}/feedback'))
        self.rate(self.e14, rating=2, comment='first')
        self.rate(self.e14, rating=3, comment='second')
        f = ExperimentFeedback.objects.get()
        self.assertEqual((f.rating, f.comment, f.context, f.attempt), (3, 'second', 'practice', None))

    def test_staff_see_ratings_without_names_and_only_their_college(self):
        ExperimentFeedback.objects.create(user=self.st, experiment=self.e18, college=self.c1, rating=2, difficulty='hard', comment='The Schild plot step is unclear')
        ExperimentFeedback.objects.create(user=self.st2, experiment=self.e14, college=self.c1, rating=5)
        other = mkuser('two-bp001', Role.STUDENT, self.c2)
        ExperimentFeedback.objects.create(user=other, experiment=self.e14, college=self.c2, rating=1, comment='From the other college')
        for u in (self.fac, self.la, self.ca):
            self.login(u)
            r = self.client.get('/feedback/')
            self.assertContains(r, 'The Schild plot step is unclear')
            self.assertContains(r, 'Lowest rated so far')
            self.assertNotContains(r, 'From the other college')
            self.assertNotContains(r, self.st.display_name)
            self.assertNotContains(r, 'BP001')
            self.assertContains(r, 'href="/feedback/" aria-current="page"')
        self.login(self.sa)
        self.assertContains(self.client.get('/feedback/'), 'From the other college')
        self.login(self.ca2)
        self.assertNotContains(self.client.get('/feedback/'), 'The Schild plot step is unclear')
        self.login(self.st)
        self.assertEqual(self.client.get('/feedback/').status_code, 403)

    def test_feedback_is_in_the_data_export_and_erased_on_deletion(self):
        ExperimentFeedback.objects.create(user=self.st, experiment=self.e18, college=self.c1, rating=4, comment='Mention of my name, Asha')
        self.login(self.st)
        data = json.loads(self.client.get('/me/data/?download=1').content)
        self.assertEqual(data['experiment_feedback'][0]['comment'], 'Mention of my name, Asha')
        anonymise_user(self.st)
        f = ExperimentFeedback.objects.get()
        self.assertEqual((f.rating, f.comment), (4, ''))

    def test_shared_demo_login_cannot_rate(self):
        with override_settings(SHARED_DEMO_USERNAMES=[self.st.username]):
            self.login(self.st)
            self.assertFalse(ctx_of(self.client.get(self.e14.url))['canRate'])
            self.assertEqual(self.rate(self.e14, rating=5).status_code, 403)


RAW_MAIL = (b'From: Asha Rao <Asha@Example.com>\r\nTo: lab@xprism.example\r\nSubject: Demo for our college\r\n'
            b'Message-ID: <in-1@example.com>\r\nDate: Mon, 02 Nov 2026 10:00:00 +0530\r\nMIME-Version: 1.0\r\n'
            b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
            b'--B\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'
            b'<html><head><style>p{color:red}</style></head><body><p>Hello team,</p><script>alert(1)</script><p>Can we book a <b>demo</b>?</p></body></html>\r\n'
            b'--B\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename="syllabus.pdf"\r\nContent-Transfer-Encoding: base64\r\n\r\nJVBERi0xLjQK\r\n--B--\r\n')


class FakeImap:
    """Stands in for imaplib.IMAP4_SSL: one mailbox with the messages given to it."""
    mails, fail, seen = [], False, None

    def __init__(self, host, port, timeout=None):
        if FakeImap.fail:
            raise OSError('connection refused')
        FakeImap.seen = {'host': host, 'port': port}

    def login(self, user, password):
        FakeImap.seen.update(user=user, password=password)
        return 'OK', [b'']

    def select(self, folder, readonly=False):
        FakeImap.seen.update(folder=folder, readonly=readonly)
        return 'OK', [b'1']

    def uid(self, command, *args):
        if command == 'search':
            FakeImap.seen['search'] = args
            return 'OK', [b' '.join(str(i + 1).encode() for i in range(len(FakeImap.mails)))]
        FakeImap.seen['fetch'] = args[1]
        return 'OK', [(b'1 (BODY[] {10}', FakeImap.mails[int(args[0]) - 1]), b')']

    def logout(self):
        FakeImap.seen['logged_out'] = True


@override_settings(IMAP_HOST='imap.xprism.example', IMAP_USER='lab@xprism.example', IMAP_PASSWORD='secret', MAILBOX_ADDRESS='lab@xprism.example')
class MailboxTests(Base):
    """The super admins' mailbox: writing in the template, receiving over IMAP, folders and replies."""
    FORM = {'to': 'asha@example.com', 'subject': 'Your demo on Monday', 'greeting': 'Asha', 'body': 'We can meet at 10 am.\n\nThe link is https://xprism.example/demo', 'signoff': 'The XPRISM team'}

    def setUp(self):
        cache.clear()
        FakeImap.mails, FakeImap.fail, FakeImap.seen = [], False, None
        patcher = mock.patch('imaplib.IMAP4_SSL', FakeImap)          # no test may reach a real mail server
        patcher.start()
        self.addCleanup(patcher.stop)
        self.login(self.sa)

    def write(self, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/platform/mailbox/compose/', {**self.FORM, **extra})

    def test_only_super_admins_reach_the_mailbox(self):
        m = mailbox.store(RAW_MAIL)
        urls = ['/platform/mailbox/', '/platform/mailbox/compose/', f'/platform/mailbox/{m.pk}/']
        for u in (self.ca, self.fac, self.st):
            self.login(u)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403, f'{u.username} {url}')
            self.assertEqual(self.client.post('/platform/mailbox/preview/', {'subject': 'x'}).status_code, 403)
            self.assertNotContains(self.client.get('/about/'), 'Mailbox')
        self.client.logout()
        self.assertEqual(self.client.get('/platform/mailbox/').status_code, 302)
        self.login(self.sa)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_a_message_is_sent_in_the_template_and_kept_in_sent(self):
        r = self.write()
        m = MailMessage.objects.get()
        self.assertRedirects(r, f'/platform/mailbox/{m.pk}/')
        self.assertEqual((m.direction, m.status, m.to, m.sent_by, m.is_read), ('out', 'sent', 'asha@example.com', self.sa, True))
        sent = mail.outbox[0]
        self.assertEqual((sent.to, sent.subject, sent.reply_to), (['asha@example.com'], 'Your demo on Monday', ['lab@xprism.example']))
        self.assertEqual(sent.extra_headers['Message-ID'], m.message_id)
        html_part = sent.alternatives[0][0]
        for text in ('Your demo on Monday', 'Hello Asha,', 'We can meet at 10 am.', 'href="https://xprism.example/demo"', 'The XPRISM team', 'cid:xprism-logo', 'You can reply to this e-mail'):
            self.assertIn(text, html_part)
        self.assertNotIn('do not reply', html_part)
        self.assertIn('Hello Asha,\n\nWe can meet at 10 am.', sent.body)
        self.assertContains(self.client.get('/platform/mailbox/?folder=sent'), 'Your demo on Monday')
        self.assertTrue(AuditLog.objects.filter(action='mail_sent').exists())

    def test_reply_to_is_always_a_real_address(self):
        # with Resend the SMTP login is the word "resend", which the IMAP settings inherit: it must never become the Reply-To
        with override_settings(MAILBOX_ADDRESS='', IMAP_USER='resend', DEFAULT_FROM_EMAIL='XPRISM <admin@xprism.example>'):
            self.assertEqual(mailbox.address(), 'admin@xprism.example')
            self.write()
            self.assertEqual(mail.outbox[0].reply_to, ['admin@xprism.example'])
            self.assertEqual(MailMessage.objects.get().status, 'sent')
        with override_settings(MAILBOX_ADDRESS='not an address', IMAP_USER='resend', DEFAULT_FROM_EMAIL='resend'):
            self.assertEqual(mailbox.address(), '')
            self.write(subject='No address to reply to')
            self.assertEqual(mail.outbox[-1].reply_to, [])
        with override_settings(MAILBOX_ADDRESS='replies@xprism.example', IMAP_USER='resend'):
            self.assertEqual(mailbox.address(), 'replies@xprism.example')
            self.assertContains(self.client.get('/platform/mailbox/compose/'), 'Replies go to <b>replies@xprism.example</b>')
        with override_settings(MAILBOX_ADDRESS='', IMAP_USER='resend', DEFAULT_FROM_EMAIL='XPRISM <no-reply@localhost>'):
            self.assertEqual(mailbox.address(), '')              # the built-in default sender is not a place to reply to
            self.assertContains(self.client.get('/platform/mailbox/compose/'), 'No reply address is set')

    def test_a_comment_after_a_value_in_env_is_not_part_of_the_value(self):
        from config.settings import env_value
        self.assertEqual(env_value(' admin@xprism.example   # where replies should go'), 'admin@xprism.example')
        self.assertEqual(env_value('"XPRISM <admin@xprism.example>"  # sender'), 'XPRISM <admin@xprism.example>')
        self.assertEqual(env_value("'pass # word'"), 'pass # word')
        self.assertEqual(env_value('re_abc#123'), 're_abc#123')        # a # inside a key is kept
        self.assertEqual(env_value(''), '')

    def test_what_the_form_refuses(self):
        self.assertContains(self.write(to='not-an-address'), 'Not a valid e-mail address')
        self.assertContains(self.write(to=', '.join(f'p{i}@example.com' for i in range(21))), 'At most 20 addresses')
        self.assertContains(self.write(body='   '), 'Write a message.')
        self.assertFalse(MailMessage.objects.exists())
        self.write(subject='Hello\nBcc: victim@example.com')            # a line break cannot add a header
        self.assertEqual(mail.outbox[0].subject, 'Hello Bcc: victim@example.com')
        self.assertEqual(mail.outbox[0].to, ['asha@example.com'])
        with override_settings(MAILBOX_MAX_PER_DAY=1):
            self.assertContains(self.write(), 'limit of 1 messages')
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend', DEBUG=False):
            self.assertContains(self.write(), 'Sending is not set up yet')
        self.assertEqual(MailMessage.objects.count(), 1)

    def test_a_failed_send_is_recorded_and_can_be_sent_again(self):
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=OSError('mail server said no')):
            self.write()
        m = MailMessage.objects.get()
        self.assertEqual((m.status, m.error), ('failed', 'mail server said no'))
        self.assertContains(self.client.get(f'/platform/mailbox/{m.pk}/'), 'This message was not sent.')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/platform/mailbox/{m.pk}/', {'action': 'resend'})
        again = MailMessage.objects.get()
        self.assertEqual((again.status, len(mail.outbox)), ('sent', 1))
        self.assertNotEqual(again.pk, m.pk)

    def test_received_mail_is_kept_as_text_only(self):
        m = mailbox.store(RAW_MAIL)
        self.assertIsNone(mailbox.store(RAW_MAIL))                      # the same message is never stored twice
        self.assertEqual((m.direction, m.from_name, m.from_email, m.subject, m.is_read), ('in', 'Asha Rao', 'asha@example.com', 'Demo for our college', False))
        self.assertIn('Can we book a demo?', m.body)
        for unsafe in ('<', 'alert(1)', 'color:red'):
            self.assertNotIn(unsafe, m.body)
        self.assertEqual(m.attachments, [{'name': 'syllabus.pdf', 'size': 9}])
        page = self.client.get(f'/platform/mailbox/{m.pk}/')
        self.assertContains(page, 'syllabus.pdf')
        self.assertContains(page, 'Attachments are not kept here')
        self.assertNotContains(page, '<script>alert(1)</script>')

    def test_text_that_looks_like_markup_is_shown_not_run(self):
        raw = RAW_MAIL.replace(b'<in-1@example.com>', b'<in-2@example.com>').split(b'--B')[0] .replace(b'multipart/mixed; boundary="B"', b'text/plain') + b'Try <script>alert(2)</script> & <img src=x onerror=1>\r\n'
        m = mailbox.store(raw)
        page = self.client.get(f'/platform/mailbox/{m.pk}/')
        self.assertContains(page, '&lt;script&gt;alert(2)&lt;/script&gt;')
        self.assertNotContains(page, '<img src=x')

    def test_new_mail_is_fetched_read_only_and_shown_as_unread(self):
        FakeImap.mails = [RAW_MAIL]
        with mock.patch('imaplib.IMAP4_SSL', FakeImap):
            r = self.client.post('/platform/mailbox/', {'action': 'check'}, follow=True)
            self.assertContains(r, '1 new message.')
            self.assertContains(self.client.post('/platform/mailbox/', {'action': 'check'}, follow=True), 'No new mail.')
        self.assertEqual((FakeImap.seen['host'], FakeImap.seen['user'], FakeImap.seen['readonly'], FakeImap.seen['fetch']), ('imap.xprism.example', 'lab@xprism.example', True, '(BODY.PEEK[])'))
        self.assertTrue(FakeImap.seen['logged_out'])
        self.assertEqual(MailMessage.objects.count(), 1)
        page = self.client.get('/platform/mailbox/')
        self.assertContains(page, 'class="is-unread"')
        self.assertContains(page, 'Mailbox <span class="xp-count">1</span>')
        self.client.get(f'/platform/mailbox/{MailMessage.objects.get().pk}/')          # opening it marks it read
        self.assertNotContains(self.client.get('/platform/mailbox/'), 'xp-count')

    def test_the_inbox_checks_by_itself_and_survives_a_dead_server(self):
        FakeImap.mails = [RAW_MAIL]
        with mock.patch('imaplib.IMAP4_SSL', FakeImap):
            self.assertContains(self.client.get('/platform/mailbox/'), 'Demo for our college')
            FakeImap.fail = True
            self.assertContains(self.client.post('/platform/mailbox/', {'action': 'check'}, follow=True), 'Could not reach the mail server')
            out = io.StringIO()
            call_command('fetch_mail', stdout=out, stderr=io.StringIO())
            self.assertIn('0 new messages', out.getvalue())
        with override_settings(IMAP_HOST=''):
            MailMessage.objects.all().delete()
            self.assertContains(self.client.get('/platform/mailbox/'), 'The inbox is not connected yet')

    def test_a_reply_joins_the_conversation(self):
        first = mailbox.store(RAW_MAIL)
        form = self.client.get(f'/platform/mailbox/compose/?reply={first.pk}').context['form']
        self.assertEqual((form['to'].value(), form['subject'].value(), form['greeting'].value()), ('asha@example.com', 'Re: Demo for our college', 'Asha Rao'))
        self.assertIn('> Hello team,', form['body'].value())
        self.write(parent=first.pk, subject='Re: Demo for our college')
        reply = MailMessage.objects.get(direction='out')
        self.assertEqual((reply.parent, reply.root, mail.outbox[0].extra_headers['In-Reply-To']), (first, first, '<in-1@example.com>'))
        later = format_datetime(timezone.now() + timezone.timedelta(seconds=5)).encode()       # the answer arrives after our reply was sent
        answer = mailbox.store(RAW_MAIL.replace(b'Mon, 02 Nov 2026 10:00:00 +0530', later).replace(b'<in-1@example.com>', b'<in-3@example.com>\r\nIn-Reply-To: ' + reply.message_id.encode()))
        self.assertEqual((answer.parent, answer.root), (reply, first))
        page = self.client.get(f'/platform/mailbox/{answer.pk}/')
        self.assertContains(page, '3 messages in this conversation')
        self.assertEqual([t.pk for t in page.context['thread']], [first.pk, reply.pk, answer.pk])

    def test_folders_stars_archive_and_trash(self):
        m = mailbox.store(RAW_MAIL)
        post = lambda **data: self.client.post('/platform/mailbox/', data, follow=True)
        post(toggle_star=m.pk)
        self.assertContains(self.client.get('/platform/mailbox/?folder=starred'), 'Demo for our college')
        self.assertContains(post(action='archive', ids=[m.pk]), '1 message archived.')
        self.assertNotContains(self.client.get('/platform/mailbox/'), 'Demo for our college')
        self.assertContains(self.client.get('/platform/mailbox/?folder=archive'), 'Demo for our college')
        self.assertContains(post(action='delete', ids=[m.pk]), 'Choose one or more messages first.')       # only the trash can delete for good
        self.assertTrue(MailMessage.objects.filter(pk=m.pk).exists())
        post(action='trash', ids=[m.pk])
        self.assertContains(self.client.get('/platform/mailbox/?folder=trash'), 'Demo for our college')
        self.assertNotContains(self.client.get('/platform/mailbox/?folder=archive'), 'Demo for our college')
        post(action='restore', ids=[m.pk])
        self.assertIsNone(MailMessage.objects.get().trashed_at)
        post(action='trash', ids=[m.pk])
        self.assertContains(post(action='empty_trash'), 'Trash emptied: 1 message deleted for good.')
        self.assertFalse(MailMessage.objects.exists())
        self.assertContains(post(action='read'), 'Choose one or more messages first.')

    def test_search_and_preview(self):
        mailbox.store(RAW_MAIL)
        mailbox.store(RAW_MAIL.replace(b'<in-1@example.com>', b'<in-4@example.com>').replace(b'Demo for our college', b'Invoice query'))
        page = self.client.get('/platform/mailbox/?q=invoice')
        self.assertContains(page, 'Invoice query')
        self.assertNotContains(page, 'Demo for our college')
        self.assertContains(self.client.get('/platform/mailbox/?q=nothing-like-this'), 'Nothing matches')
        doc = self.client.post('/platform/mailbox/preview/', {'subject': 'Hi <b>', 'body': 'One\n\nTwo', 'greeting': 'Asha', 'signoff': ''}).json()['html']
        for text in ('Hi &lt;b&gt;', 'Hello Asha,', '>One</p>', '>Two</p>', 'The XPRISM team', '/assets/img/xprism-lockup.png'):
            self.assertIn(text, doc)
        self.assertNotIn('cid:', doc)

    def test_mail_is_erased_with_the_account(self):
        mailbox.store(RAW_MAIL)
        self.write()
        mailbox.store(RAW_MAIL.replace(b'<in-1@example.com>', b'<in-5@example.com>').replace(b'Asha@Example.com', b'someone@else.example'))
        u = mkuser('asha@example.com', Role.STUDENT, is_trial_account=True, email='asha@example.com')
        anonymise_user(u)
        self.assertEqual(list(MailMessage.objects.values_list('from_email', flat=True)), ['someone@else.example'])


RESEND_MAIL = {
    'object': 'email', 'id': 'e-1', 'to': ['admin@xprism.example'], 'from': 'asha@example.com', 'created_at': '2026-11-02T04:30:00.000Z', 'subject': 'Demo for our college',
    'html': '<p>Hello team,</p><script>alert(1)</script><p>Can we book a <b>demo</b>?</p>', 'text': None, 'message_id': '<rs-1@example.com>',
    'headers': {'from': 'Asha Rao <Asha@Example.com>', 'mime-version': '1.0'},
    'attachments': [{'id': 'a-1', 'filename': 'syllabus.pdf', 'content_type': 'application/pdf', 'size': 13264}],
}


@override_settings(RESEND_RECEIVE=True, RESEND_API_KEY='re_test', RESEND_WEBHOOK_SECRET='whsec_' + 'c2VjcmV0LWtleS1mb3ItdGVzdHM=', IMAP_HOST='', MAILBOX_ADDRESS='admin@xprism.example')
class ResendReceivingTests(Base):
    """Mail received through Resend, which has no IMAP: read from its Receiving API, at once when its webhook calls."""

    def setUp(self):
        cache.clear()
        self.mails, self.calls, self.error = [dict(RESEND_MAIL)], [], None
        patcher = mock.patch('lab.mailbox._resend', self.api)          # no test may reach Resend
        patcher.start()
        self.addCleanup(patcher.stop)
        self.login(self.sa)

    def api(self, path):
        self.calls.append(path)
        if self.error:
            raise self.error
        if path.startswith('/emails/receiving?'):
            return {'object': 'list', 'has_more': False, 'data': [{k: v for k, v in m.items() if k not in ('html', 'text', 'headers')} for m in self.mails]}
        return next(m for m in self.mails if path.endswith('/' + m['id']))

    def sign(self, body, secret=None, stamp=None, msg_id='msg_1'):
        import base64, hashlib, hmac, time
        stamp = str(int(stamp or time.time()))
        key = base64.b64decode((secret or settings.RESEND_WEBHOOK_SECRET).split('_', 1)[1])
        sig = base64.b64encode(hmac.new(key, f'{msg_id}.{stamp}.'.encode() + body, hashlib.sha256).digest()).decode()
        return {'HTTP_SVIX_ID': msg_id, 'HTTP_SVIX_TIMESTAMP': stamp, 'HTTP_SVIX_SIGNATURE': f'v1,wrong v1,{sig}'}

    def test_mail_comes_in_from_resend_as_text_only(self):
        r = self.client.post('/platform/mailbox/', {'action': 'check'}, follow=True)
        self.assertContains(r, '1 new message.')
        m = MailMessage.objects.get()
        self.assertEqual((m.direction, m.from_name, m.from_email, m.to, m.subject, m.message_id), ('in', 'Asha Rao', 'asha@example.com', 'admin@xprism.example', 'Demo for our college', '<rs-1@example.com>'))
        self.assertIn('Can we book a demo?', m.body)
        self.assertNotIn('alert(1)', m.body)
        self.assertEqual(m.attachments, [{'name': 'syllabus.pdf', 'size': 13264}])
        self.assertEqual(self.calls[:2], ['/emails/receiving?limit=100', '/emails/receiving/e-1'])
        self.calls.clear()
        self.assertContains(self.client.post('/platform/mailbox/', {'action': 'check'}, follow=True), 'No new mail.')
        self.assertEqual(set(self.calls), {'/emails/receiving?limit=100'})   # a message already here is not downloaded again
        self.assertContains(self.client.get('/platform/mailbox/'), 'Check for new mail')

    def test_an_answer_through_resend_joins_our_message(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/platform/mailbox/compose/', {'to': 'asha@example.com', 'subject': 'Your demo', 'body': 'Monday at 10?', 'signoff': ''})
        ours = MailMessage.objects.get()
        self.assertEqual(mail.outbox[0].reply_to, ['admin@xprism.example'])
        self.mails = [{**RESEND_MAIL, 'id': 'e-2', 'message_id': '<rs-2@example.com>', 'subject': 'Re: Your demo', 'text': 'Monday works.', 'html': None,
                       'headers': {'From': 'Asha Rao <asha@example.com>', 'In-Reply-To': ours.message_id}}]
        mailbox.fetch()
        answer = MailMessage.objects.get(direction='in')
        self.assertEqual((answer.parent, answer.root, answer.body), (ours, ours, 'Monday works.'))

    def test_a_key_that_cannot_read_mail_is_explained(self):
        import urllib.error
        self.error = urllib.error.HTTPError('https://api.resend.com/emails/receiving', 401, 'Unauthorized', {}, None)
        self.assertContains(self.client.post('/platform/mailbox/', {'action': 'check'}, follow=True), 'Create a key with full access')
        self.error = OSError('timed out')
        self.assertContains(self.client.post('/platform/mailbox/', {'action': 'check'}, follow=True), 'Could not reach Resend')
        with override_settings(RESEND_RECEIVE=False):
            self.assertContains(self.client.get('/platform/mailbox/'), 'The inbox is not connected yet')

    def test_webhook_brings_mail_in_only_when_resend_signed_it(self):
        self.client.logout()
        body = json.dumps({'type': 'email.received', 'data': {'email_id': 'e-1'}}).encode()
        post = lambda **headers: self.client.post('/api/resend/inbound', data=body, content_type='application/json', **headers)
        self.assertEqual(post().status_code, 401)
        self.assertEqual(post(**self.sign(body, secret='whsec_' + 'b3RoZXItc2VjcmV0')).status_code, 401)
        self.assertEqual(post(**self.sign(body, stamp=1_000_000)).status_code, 401)              # an old request replayed
        self.assertEqual(post(**self.sign(b'{"type": "something else"}')).status_code, 401)      # signed for a different body
        self.assertFalse(MailMessage.objects.exists())
        r = post(**self.sign(body))
        self.assertEqual((r.status_code, r.json()), (200, {'ok': True, 'new': 1}))
        self.assertEqual(MailMessage.objects.get().subject, 'Demo for our college')
        self.assertEqual(self.client.get('/api/resend/inbound').status_code, 405)
        with override_settings(RESEND_WEBHOOK_SECRET=''):
            self.assertEqual(post(**self.sign(body, secret='whsec_' + 'c2VjcmV0LWtleS1mb3ItdGVzdHM=')).status_code, 404)


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
@override_settings(FREE_MONTH_AUTO_APPROVE=False)
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

    @override_settings(FREE_MONTH_MAX_PER_HOUR=5)
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
        year = one_month_after(timezone.localdate())
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
        self.assertEqual(t.subscribed_until, one_month_after(end))
        self.assertEqual(User.objects.filter(email='t@example.com').count(), 1)
        self.assertNotIn('/accounts/password/reset/', mail.outbox[0].body)

    def test_approve_college_creates_college_and_admin(self):
        self.apply(kind='college', institution='Rao College of Pharmacy')
        self.decide(FreeYearApplication.objects.get(), college='new')
        c = College.objects.get(name='Rao College of Pharmacy')
        admin = User.objects.get(college=c, role=Role.COLLEGE_ADMIN)
        self.assertEqual(c.subscription_until, one_month_after(timezone.localdate()))
        self.assertTrue(c.is_subscribed)
        self.assertEqual((admin.username, admin.email), (f'{c.code}-admin', 'asha@example.com'))

    def test_approve_college_renews_a_lapsed_college_without_new_admin(self):
        College.objects.filter(pk=self.c2.pk).update(subscription_until=timezone.localdate() - timezone.timedelta(days=9))
        n = User.objects.count()
        self.apply(kind='college', institution='College Two')
        self.decide(FreeYearApplication.objects.get(), college=self.c2.pk)
        self.c2.refresh_from_db()
        self.assertEqual(self.c2.subscription_until, one_month_after(timezone.localdate()))
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

    def test_month_end_dates(self):
        self.assertEqual(one_month_after(datetime.date(2028, 1, 31)), datetime.date(2028, 2, 29))
        self.assertEqual(one_month_after(datetime.date(2027, 12, 15)), datetime.date(2028, 1, 15))
        self.assertEqual(one_month_after(datetime.date(2027, 3, 31)), datetime.date(2027, 4, 30))


@override_settings(SUBSCRIPTION_CONTACT='owner@example.com')
class FreeMonthAutoApprovalTests(Base):
    """An application is approved the moment it is made, unless it would change something that already exists."""
    FORM = {'kind': 'individual', 'name': 'Asha Rao', 'email': 'Asha@Example.com', 'institution': 'Rao College', 'occupation': 'faculty', 'consent': 'on'}

    def setUp(self):
        cache.clear()

    def apply(self, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/free-year/apply', {**self.FORM, **extra})

    def test_individual_gets_an_account_and_a_month_straight_away(self):
        r = self.apply()
        self.assertEqual(r.json(), {'ok': True, 'email': 'asha@example.com', 'auto': True})
        app = FreeYearApplication.objects.get()
        u = User.objects.get(username='asha@example.com')
        self.assertEqual((app.status, app.user, app.reviewed_by, app.review_note), (FreeYearApplication.APPROVED, u, None, 'Approved automatically.'))
        self.assertEqual(u.subscribed_until, one_month_after(timezone.localdate()))
        self.assertTrue(u.has_full_access and u.is_trial_account and u.email_verified)
        self.assertEqual([m.to for m in mail.outbox], [['asha@example.com'], ['owner@example.com']])
        self.assertIn('/accounts/password/reset/', mail.outbox[0].body)
        self.assertIn('approved automatically', mail.outbox[1].body)
        self.assertNotIn('/accounts/password/reset/', mail.outbox[1].body)
        self.assertTrue(AuditLog.objects.filter(action='free_year_auto_approved').exists())
        link = re.search(r'http://\S+/accounts/password/reset/\S+', mail.outbox[0].body).group(0)
        self.assertEqual(self.client.get(link.split('testserver')[-1] if 'testserver' in link else '/' + link.split('/', 3)[3]).status_code, 302)

    def test_signed_in_trial_user_is_unlocked_at_once(self):
        trial = mkuser('t@example.com', Role.STUDENT, is_trial_account=True, email='t@example.com')
        self.login(trial)
        self.apply(email='someone-else@example.com')
        trial.refresh_from_db()
        self.assertTrue(trial.has_full_access)
        self.assertEqual(FreeYearApplication.objects.get().email, 't@example.com')
        self.assertFalse(User.objects.filter(email='someone-else@example.com').exists())
        self.assertNotIn('/accounts/password/reset/', mail.outbox[0].body)      # they already have a password
        self.assertNotContains(self.client.get('/modules/'), 'id="freeYearModal"')

    def test_new_college_is_created_with_its_admin(self):
        self.apply(kind='college', institution='Rao College of Pharmacy')
        app = FreeYearApplication.objects.get()
        college = College.objects.get(name='Rao College of Pharmacy')
        admin = User.objects.get(college=college)
        self.assertEqual((app.status, app.awarded_college, admin.role), (FreeYearApplication.APPROVED, college, Role.COLLEGE_ADMIN))
        self.assertEqual(college.subscription_until, one_month_after(timezone.localdate()))
        self.assertIn(admin.username, mail.outbox[0].body)

    def test_existing_college_is_left_alone_and_the_applicant_gets_the_month(self):
        until = self.c1.subscription_until
        self.apply(kind='college', institution='  college one ', college=str(self.c1.pk))
        app = FreeYearApplication.objects.get()
        self.assertEqual((app.status, app.awarded_college), (FreeYearApplication.APPROVED, None))
        self.assertIn('applicant only', app.review_note)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.subscription_until, until)
        self.assertEqual(College.objects.filter(name__iexact='college one').count(), 1)
        u = User.objects.get(username='asha@example.com')
        self.assertTrue(u.has_full_access)
        self.assertIsNone(u.college)
        self.assertEqual([m.to for m in mail.outbox], [['asha@example.com'], ['owner@example.com']])

    def test_a_posted_college_id_cannot_redirect_the_award(self):
        self.apply(kind='college', institution='Brand New College', college=str(self.c2.pk))
        self.assertEqual(FreeYearApplication.objects.get().awarded_college.name, 'Brand New College')
        self.c2.refresh_from_db()
        self.assertIsNone(self.c2.subscription_until)

    def test_member_of_a_lapsed_college_gets_the_month_personally(self):
        self.c1.subscription_active = False
        self.c1.save()
        self.st.email = 'bp001@example.com'
        self.st.save()
        self.login(self.st)
        self.apply(kind='college', institution='Some Other Name')
        self.assertEqual(FreeYearApplication.objects.get().status, FreeYearApplication.APPROVED)
        self.assertFalse(College.objects.filter(name='Some Other Name').exists())
        self.st.refresh_from_db()
        self.assertTrue(self.st.has_full_access)
        self.assertFalse(User.objects.get(pk=self.st2.pk).has_full_access)       # the rest of the college is unchanged

    def test_someone_still_waiting_is_approved_when_they_apply_again(self):
        with override_settings(FREE_MONTH_AUTO_APPROVE=False):
            self.apply()
        app = FreeYearApplication.objects.get()
        self.assertEqual(app.status, FreeYearApplication.PENDING)
        mail.outbox.clear()
        self.apply()
        app.refresh_from_db()
        self.assertEqual((app.status, FreeYearApplication.objects.count()), (FreeYearApplication.APPROVED, 1))
        self.assertTrue(User.objects.get(username='asha@example.com').has_full_access)
        self.assertEqual(mail.outbox[0].to, ['asha@example.com'])

    def test_super_admin_clears_the_waiting_list_in_one_step(self):
        with override_settings(FREE_MONTH_AUTO_APPROVE=False):
            self.apply()
            self.apply(email='ravi@example.com', name='Ravi Kumar', kind='college', institution='Kumar College of Pharmacy')
            mkuser('gone@example.com', Role.STUDENT, is_trial_account=True, email='gone@example.com', is_active=False)
            self.apply(email='gone@example.com')
        self.login(self.sa)
        self.assertContains(self.client.get('/platform/free-year/'), 'Approve all 3 waiting')
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post('/platform/free-year/', {'decision': 'approve_waiting'}, follow=True)
        self.assertContains(r, '2 applications approved. 1 still needs your decision')
        self.assertEqual(sorted(FreeYearApplication.objects.values_list('status', flat=True)), ['approved', 'approved', 'pending'])
        self.assertTrue(College.objects.filter(name='Kumar College of Pharmacy').exists())
        self.login(self.fac)
        self.assertEqual(self.client.post('/platform/free-year/', {'decision': 'approve_waiting'}).status_code, 403)

    def test_a_whole_department_can_apply_from_one_network(self):
        for i in range(12):
            self.assertEqual(self.apply(email=f'faculty{i}@example.com').json().get('ok'), True)
        self.assertEqual(FreeYearApplication.objects.filter(status=FreeYearApplication.APPROVED).count(), 12)
        with override_settings(FREE_MONTH_MAX_PER_HOUR=12):
            self.assertEqual(self.apply(email='one-more@example.com').status_code, 429)

    def test_deactivated_account_waits(self):
        mkuser('asha@example.com', Role.STUDENT, is_trial_account=True, email='asha@example.com', is_active=False)
        self.apply()
        self.assertEqual(FreeYearApplication.objects.get().status, FreeYearApplication.PENDING)
        self.assertIsNone(User.objects.get(username='asha@example.com').subscribed_until)

    def test_one_month_per_address_and_the_same_answer_each_time(self):
        first = self.apply().json()
        mail.outbox.clear()
        again = self.apply().json()
        self.assertEqual(first, again)
        self.assertEqual(FreeYearApplication.objects.count(), 1)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(User.objects.get(username='asha@example.com').subscribed_until, one_month_after(timezone.localdate()))

    def test_pop_up_says_what_will_happen(self):
        self.assertContains(self.client.get('/'), 'Most applications are approved straight away.')
        with override_settings(FREE_MONTH_AUTO_APPROVE=False):
            self.assertContains(self.client.get('/'), 'Our super admin reviews every application.')


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
        for text in ('The Management and Administration', 'About XPRISM', 'Modules in XPRISM (42)', 'Isolated tissue experiments', 'Aaron Innovations', 'Kolkata, India', 'developed by Dr. Vara Prasad Saka', self.e14.title):
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


class SignInTests(Base):
    def make(self, **kw):
        u = User.objects.create_user(username=kw.pop('username', 'asha@example.com'), password='Strong#Pass77', role=Role.STUDENT, consent_version=settings.POLICY_VERSION, ethics_version=settings.ETHICS_VERSION, **kw)
        return u

    def sign_in(self, name, password='Strong#Pass77', query=''):
        return self.client.post('/accounts/login/' + query, {'username': name, 'password': password})

    def test_capitals_and_spaces_in_the_username_do_not_matter(self):
        self.make(is_trial_account=True, email='asha@example.com')
        r = self.sign_in('  Asha@Example.COM ')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='asha@example.com').pk)

    def test_email_signs_in_to_a_college_account(self):
        self.make(username='clg-bp1', email='neha@example.com')
        self.assertEqual(self.sign_in('neha@example.com').status_code, 302)

    def test_a_shared_email_does_not_pick_an_account(self):
        self.make(username='clg-a', email='same@example.com')
        self.make(username='clg-b', email='same@example.com')
        self.assertContains(self.sign_in('same@example.com'), 'Incorrect username')

    def test_failed_sign_in_never_shows_the_matched_username(self):
        self.make(username='clg-bp2', email='hidden@example.com')
        r = self.sign_in('hidden@example.com', password='wrong')
        self.assertContains(r, 'hidden@example.com')
        self.assertNotContains(r, 'clg-bp2')

    def test_next_survives_sign_in_and_rejects_other_sites(self):
        self.make(email='asha@example.com')
        self.assertEqual(self.sign_in('asha@example.com', query='?next=/about/')['Location'], '/about/')
        self.client.logout()
        self.assertEqual(self.sign_in('asha@example.com', query='?next=https://evil.example/')['Location'], '/home/')

    def test_next_is_carried_between_the_sign_in_pages(self):
        r = self.client.get('/accounts/login/?next=/modules/')
        self.assertContains(r, '/accounts/trial/?next=/modules/')
        self.assertContains(r, '/accounts/signup/?next=/modules/')
        self.assertContains(self.client.get('/accounts/trial/?next=/modules/'), 'name="next" value="/modules/"')

    def test_after_login_the_button_becomes_sign_out(self):
        self.login(self.st)
        r = self.client.get('/about/')
        self.assertContains(r, '>Sign out</button>', count=1)
        self.assertNotContains(r, '>Login</a>')

    def test_nav_shows_sign_in_and_contact(self):
        r = self.client.get('/about/')
        self.assertContains(r, '>Login</a>', count=1)
        self.assertNotContains(r, 'Sign out')
        self.assertNotContains(r, 'xh-signup')
        self.assertContains(r, 'href="/contact/"')


class ContactTests(Base):
    FORM = {'topic': 'demo', 'subtopic': 'demo.online', 'name': 'Asha Rao', 'email': 'Asha@Example.com', 'phone': '', 'institution': 'ABC College', 'message': 'Please show us the lab.', 'consent': 'on'}

    def send(self, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/contact/', {**self.FORM, **extra})

    def test_request_reaches_the_super_admin_and_the_sender_is_told(self):
        r = self.send()
        item = ContactRequest.objects.get()
        self.assertEqual(r['Location'], f'/contact/?sent={item.reference}')
        self.assertEqual((item.topic, item.subtopic, item.email, item.status), ('demo', 'online', 'asha@example.com', ContactRequest.NEW))
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(item.reference, mail.outbox[1].subject)
        self.assertContains(self.client.get(r['Location']), item.reference)
        self.login(self.sa)
        page = self.client.get('/platform/contact/')
        self.assertContains(page, 'Asha Rao')
        self.assertContains(page, 'Live online demo')
        self.assertEqual(self.client.get('/platform/').context['stats']['contact'], 1)

    def test_contact_page_shows_no_personal_address(self):
        page = self.client.get('/contact/').content.decode()
        self.assertNotIn(settings.LEGAL['contact_email'], page)
        self.assertNotIn('gmail.com', page)

    def test_alert_is_e_mailed_to_the_super_admins(self):
        User.objects.filter(pk=self.sa.pk).update(email='boss@example.com')
        self.send()
        self.assertIn('boss@example.com', mail.outbox[0].to)
        self.assertIn('New contact request', mail.outbox[0].subject)

    def test_subtopic_must_belong_to_the_subject(self):
        self.assertEqual(self.send(topic='billing').status_code, 200)
        self.assertFalse(ContactRequest.objects.exists())

    def test_a_quotation_needs_an_institution(self):
        self.assertContains(self.send(topic='quotation', subtopic='quotation.college', institution=''), 'tell us your college')
        self.assertFalse(ContactRequest.objects.exists())

    def test_every_subtopic_is_accepted(self):
        from .contact import TOPICS
        for key, _, subs in TOPICS:
            for sub, _label in subs:
                ContactRequest.objects.all().delete()
                cache.clear()
                self.assertEqual(self.send(topic=key, subtopic=f'{key}.{sub}').status_code, 302, (key, sub))

    def test_bots_and_floods_are_stopped(self):
        self.send(website='http://spam.example')
        self.assertFalse(ContactRequest.objects.exists())
        for i in range(10):
            self.send(email=f'a{i}@example.com')
        self.assertEqual(self.send(email='b@example.com').status_code, 200)
        self.assertEqual(ContactRequest.objects.count(), 10)

    def test_super_admin_resolves_and_replies(self):
        self.send()
        item = ContactRequest.objects.get()
        mail.outbox.clear()
        self.login(self.sa)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/platform/contact/', {'id': item.pk, 'status': 'resolved', 'note': 'Booked', 'reply': 'See you on Monday.'})
        item.refresh_from_db()
        self.assertEqual((item.status, item.admin_note, item.reply, item.handled_by), ('resolved', 'Booked', 'See you on Monday.', self.sa))
        self.assertIsNotNone(item.resolved_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['asha@example.com'])
        self.client.get('/platform/contact/')       # shows, and so clears, the confirmation message
        self.assertNotContains(self.client.get('/platform/contact/'), item.reference)
        self.assertContains(self.client.get('/platform/contact/?status=all'), item.reference)
        self.client.post('/platform/contact/', {'id': item.pk, 'status': 'in_progress'})
        item.refresh_from_db()
        self.assertIsNone(item.resolved_at)

    def test_only_one_menu_item_is_highlighted_in_the_inbox(self):
        self.login(self.sa)
        for url in ('/platform/contact/', '/platform/colleges/'):
            self.assertContains(self.client.get(url), 'aria-current="page"', count=1)

    def test_only_super_admins_see_the_inbox(self):
        self.assertEqual(self.client.get('/platform/contact/').status_code, 302)
        self.login(self.st)
        self.assertEqual(self.client.get('/platform/contact/').status_code, 403)

    def test_message_is_escaped_in_the_inbox(self):
        self.send(message='<script>alert(1)</script>')
        self.login(self.sa)
        self.assertNotContains(self.client.get('/platform/contact/'), '<script>alert(1)</script>')


class AssetVersionTests(Base):
    """Long-cached assets must get a new URL when the file changes."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'css').mkdir()
        (self.root / 'js').mkdir()
        for name in ('css/theme.css', 'js/bridge.js', 'js/viva.js'):
            (self.root / name).write_text('x')
        over = override_settings(STATIC_ROOT=self.root)
        over.enable()
        self.addCleanup(over.disable)

    def stamp(self, name):
        return int((self.root / name).stat().st_mtime)

    def test_app_pages_version_their_stylesheet(self):
        self.assertContains(self.client.get('/contact/'), f'/assets/css/theme.css?v={self.stamp("css/theme.css")}"')

    def test_url_changes_when_the_file_changes(self):
        s = VersionedStaticFilesStorage(location=self.root, base_url='/assets/')
        before = s.url('css/theme.css')
        os.utime(self.root / 'css/theme.css', (2000000000, 2000000000))
        self.assertNotEqual(before, s.url('css/theme.css'))
        self.assertEqual(s.url('css/theme.css'), '/assets/css/theme.css?v=2000000000')

    def test_missing_file_keeps_a_plain_url(self):
        s = VersionedStaticFilesStorage(location=self.root, base_url='/assets/')
        self.assertEqual(s.url('css/none.css'), '/assets/css/none.css')

    def test_experiment_pages_version_their_scripts_and_styles(self):
        self.login(self.fac)
        r = self.client.get(self.e14.url)
        self.assertContains(r, f'/assets/js/bridge.js?v={self.stamp("js/bridge.js")}"')
        self.assertContains(r, f'/assets/css/theme.css?v={self.stamp("css/theme.css")}"')


class SiteTagTests(Base):
    def test_robots_and_sitemap(self):
        r = self.client.get('/robots.txt')
        self.assertEqual(r['Content-Type'], 'text/plain; charset=utf-8')
        for text in ('Disallow: /platform/', 'Disallow: /accounts/', 'Disallow: /admin/', f'Sitemap: {settings.SITE_URL.rstrip("/")}/sitemap.xml'):
            self.assertContains(r, text)
        s = self.client.get('/sitemap.xml')
        self.assertIn('application/xml', s['Content-Type'])
        self.assertContains(s, '/contact/</loc>')
        self.assertNotContains(s, '/platform/')
        self.assertNotContains(s, '/experiments/')

    def test_public_pages_are_indexable_and_private_ones_are_not(self):
        self.assertContains(self.client.get('/about/'), '<meta name="robots" content="index, follow">')
        self.assertContains(self.client.get('/accounts/login/'), '<meta name="robots" content="noindex, nofollow">')
        home = self.client.get('/')
        self.assertContains(home, 'rel="canonical"')
        self.assertContains(home, 'property="og:image"')
        self.assertContains(home, 'application/ld+json')

    def test_noindex_switch_closes_the_whole_site(self):
        with self.settings(SEO={**settings.SEO, 'noindex': True}):
            self.assertContains(self.client.get('/robots.txt'), 'Disallow: /')
            self.assertNotContains(self.client.get('/sitemap.xml'), '<loc>')
            self.assertContains(self.client.get('/'), 'noindex, nofollow')

    def test_verification_tags_come_from_settings(self):
        with self.settings(SEO={**settings.SEO, 'google_verification': 'abcDEF123456', 'bing_verification': 'BING123456789'}):
            r = self.client.get('/')
            self.assertContains(r, '<meta name="google-site-verification" content="abcDEF123456">')
            self.assertContains(r, '<meta name="msvalidate.01" content="BING123456789">')

    def test_cookie_banner_on_every_page_with_analytics_off(self):
        for url in ('/', '/accounts/login/', '/contact/', '/privacy/'):
            r = self.client.get(url)
            self.assertContains(r, 'id="cookieBanner"')
            self.assertContains(r, 'data-cookie="essential"')
            self.assertContains(r, 'data-cookie-settings')
            self.assertNotContains(r, 'data-cookie="granted"')
            self.assertNotContains(r, 'googletagmanager')
        self.login(self.st)
        self.assertContains(self.client.get('/modules/'), 'id="cookieBanner"')

    def test_cookie_banner_asks_only_where_analytics_can_run(self):
        with self.settings(GOOGLE_ANALYTICS_ID='G-ABC1234'):
            home = self.client.get('/')
            self.assertContains(home, 'data-cookie="granted"')
            self.assertContains(home, 'data-cookie="denied"')
            self.assertContains(self.client.get('/privacy/'), 'Google Analytics')
            login = self.client.get('/accounts/login/')
            self.assertContains(login, 'data-cookie="essential"')
            self.assertNotContains(login, 'googletagmanager')
            self.login(self.st)
            modules = self.client.get('/modules/')
            self.assertNotContains(modules, 'data-cookie="granted"')
            self.assertNotContains(modules, 'googletagmanager')

    def test_experiment_pages_have_no_banner(self):
        self.login(self.sa)
        self.assertNotContains(self.client.get(Experiment.objects.get(no=1).url), 'cookieBanner')

    def test_policy_denies_analytics_while_it_is_off(self):
        self.assertContains(self.client.get('/privacy/'), 'We do not use analytics')

