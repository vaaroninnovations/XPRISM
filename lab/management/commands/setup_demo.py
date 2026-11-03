import random

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from lab.models import Assignment, Attempt, Batch, College, DataRequest, Enrollment, Experiment, Role, User

COLLEGE_CODE = 'xprism-demo'
PASSWORD = 'Xprism@2026'
ACCOUNTS = [('xprismadmin', 'College', 'Admin', Role.COLLEGE_ADMIN),
            ('xprismfaculty', 'Faculty', 'Demo', Role.FACULTY),
            ('xprismassistant', 'Lab', 'Assistant', Role.LAB_ASSISTANT),
            ('xprismdemo', 'Student', 'Demo', Role.STUDENT)]
# experiment no, exam mode, time limit (min), sample results shown to staff
ASSIGNMENTS = [(4, False, None, [['Mean fall-off time, basal (s)', '178.4'], ['Mean fall-off time, after drug (s)', '46.2'], ['Reduction (%)', '74.1']]),
               (18, False, None, [['Dose ratio at 1 nM antagonist', '9.6'], ['pA2 estimate', '8.9']]),
               (21, True, 45, [])]


class Command(BaseCommand):
    help = 'Create the public demo logins and sample class, or put them back as they were. Safe to run every night; touches only the demo college.'

    @transaction.atomic
    def handle(self, *a, **o):
        now = timezone.now()
        c, _ = College.objects.update_or_create(code=COLLEGE_CODE, defaults={
            'name': 'XPRISM Demo College', 'location_text': 'Shared demo', 'contact_email': '', 'grievance_officer': '', 'grievance_email': '',
            'is_active': True, 'subscription_active': True, 'subscription_until': None})
        c.disabled_experiments.clear()
        names = [x[0] for x in ACCOUNTS]
        Batch.objects.filter(college=c).delete()
        DataRequest.objects.filter(college=c).delete()
        User.objects.filter(college=c).exclude(username__in=names).delete()

        users = {}
        for username, first, last, role in ACCOUNTS:
            u, _ = User.objects.get_or_create(username=username)
            u.first_name, u.last_name, u.role, u.college, u.email = first, last, role, c, ''
            u.must_change_password, u.is_trial_account, u.is_active, u.anonymised = False, False, True, False
            u.failed_logins, u.locked_until, u.subscribed_until = 0, None, None
            u.set_password(PASSWORD)
            u.save()
            users[role] = u
        fac = users[Role.FACULTY]

        # joining is off: a class code that anyone can read must not open accounts in this college
        b = Batch.objects.create(college=c, name='B.Pharm Section A', join_enabled=False, created_by=fac)
        b.faculty.add(fac)
        Enrollment.objects.create(batch=b, student=users[Role.STUDENT])
        samples = []
        for i in range(1, 7):
            s = User(username=f'{COLLEGE_CODE}-sample{i}', first_name='Sample', last_name=f'Student {i}', role=Role.STUDENT, college=c, roll_no=f'DEMO{i:03d}')
            s.set_unusable_password()
            s.save()
            Enrollment.objects.create(batch=b, student=s)
            samples.append(s)

        rng = random.Random(2026)
        for no, exam, limit, rows in ASSIGNMENTS:
            e = Experiment.objects.get(no=no)
            x = Assignment.objects.create(batch=b, experiment=e, opens_at=now - timezone.timedelta(days=7), due_at=now + timezone.timedelta(days=14),
                                          exam_mode=exam, time_limit_min=limit, max_attempts=99, created_by=fac)
            if not rows:
                continue
            for i, s in enumerate(samples[:5]):
                vs = rng.randint(5, 10)
                at = Attempt(assignment=x, student=s, status=Attempt.SUBMITTED, started_at=now - timezone.timedelta(days=2, hours=1), submitted_at=now - timezone.timedelta(days=2),
                             viva_score=vs, viva_total=10, completion=True,
                             payload={'results': {'rows': rows, 'text': 'Sample submission created for this demo.'},
                                      'viva': {'score': vs, 'total': 10, 'items': [{'i': n, 'q': f'Sample viva question {n + 1}', 'chosen': 'A', 'correct': 'A' if n < vs else 'B', 'ok': n < vs} for n in range(10)]}})
                at.compute_auto_score()
                if i < 2:       # some already marked, the rest waiting in the faculty's queue
                    at.status, at.graded_by, at.graded_at, at.feedback = Attempt.GRADED, fac, now - timezone.timedelta(days=1), 'Good work. Sample feedback for this demo.'
                at.save()

        self.stdout.write(self.style.SUCCESS(f'Demo ready at "{c.name}", password {PASSWORD}:'))
        for username, _, _, role in ACCOUNTS:
            self.stdout.write(f'  {Role(role).label}: {username}')
