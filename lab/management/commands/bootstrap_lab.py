import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from lab.models import Assignment, Batch, College, Enrollment, Experiment, Role, User



class Command(BaseCommand):
    help = 'Load the experiment catalogue; optionally create the platform super admin and a demo college.'

    def add_arguments(self, p):
        p.add_argument('--admin-username')
        p.add_argument('--admin-password')
        p.add_argument('--admin-email', default='')
        p.add_argument('--demo-data', action='store_true', help='Create a demo college with staff, students, a batch and assignments')

    @transaction.atomic
    def handle(self, *a, **o):
        mods = json.loads((Path(__file__).resolve().parents[2] / 'modules.json').read_text(encoding='utf-8'))
        for m in mods:
            e, created = Experiment.objects.get_or_create(no=m['no'], defaults={'slug': m['slug'], 'title': m['title'], 'category': m['cat'], 'description': m.get('description', '')})
            if not created:
                e.slug, e.title, e.category, e.description = m['slug'], m['title'], m['cat'], m.get('description', '')
                e.save()
        self.stdout.write(self.style.SUCCESS(f'{len(mods)} experiments in catalogue.'))
        if o['admin_username']:
            u, created = User.objects.get_or_create(username=o['admin_username'], defaults={'email': o['admin_email']})
            u.role, u.is_superuser, u.email = Role.SUPERADMIN, True, o['admin_email'] or u.email
            if o['admin_password']:
                u.set_password(o['admin_password'])
            u.save()
            self.stdout.write(self.style.SUCCESS(f'Super admin "{u.username}" {"created" if created else "updated"}.'))
        if o['demo_data']:
            self.demo()

    def demo(self):
        c, _ = College.objects.get_or_create(code='demo', defaults={'name': 'Demo College of Pharmacy', 'location_text': 'Rajouri Garden New Delhi', 'grievance_officer': 'Dr. Vara Prasad Saka', 'grievance_email': 'grievance@example.com'})

        def mk(username, first, last, role, pw, **kw):
            u, _ = User.objects.get_or_create(username=username, defaults={'first_name': first, 'last_name': last, 'role': role, 'college': c, **kw})
            u.role, u.college = role, c
            u.set_password(pw)
            u.save()
            return u
        mk('trial-demo@example.com', 'Trial', 'Visitor', Role.STUDENT, 'Demo@Trial2026', is_trial_account=True, email='trial-demo@example.com', institution='Any College')
        User.objects.filter(username='trial-demo@example.com').update(college=None)
        cadmin = mk('demo-admin', 'College', 'Admin', Role.COLLEGE_ADMIN, 'Demo@Admin2026')
        fac = mk('demo-faculty', 'Vara Prasad', 'Saka', Role.FACULTY, 'Demo@Faculty2026')
        mk('demo-assistant', 'Lab', 'Assistant', Role.LAB_ASSISTANT, 'Demo@Assist2026')
        Batch.objects.filter(college=c, name='B.Pharm Sem VI, Section A').update(name='B.Pharm Section A')    # earlier demo name
        b, _ = Batch.objects.get_or_create(college=c, name='B.Pharm Section A', defaults={'created_by': fac})
        b.faculty.add(fac)
        for i in range(1, 6):
            s = mk(f'demo-bp{i:03d}', f'Student{i}', 'Demo', Role.STUDENT, 'Demo@Student2026', roll_no=f'BP{i:03d}')
            Enrollment.objects.get_or_create(batch=b, student=s)
        now = timezone.now()
        for no, exam in ((18, False), (14, False), (21, True)):
            e = Experiment.objects.get(no=no)
            Assignment.objects.get_or_create(batch=b, experiment=e, defaults={'due_at': now + timezone.timedelta(days=7), 'exam_mode': exam, 'time_limit_min': 45 if exam else None, 'max_attempts': 1 if exam else 2, 'created_by': fac})
        self.stdout.write(self.style.SUCCESS(f'Demo college ready. Class code for students to join: {b.class_code}'))
        self.stdout.write('  demo-admin / Demo@Admin2026 • demo-faculty / Demo@Faculty2026 • demo-assistant / Demo@Assist2026 • demo-bp001..005 / Demo@Student2026 • trial-demo@example.com / Demo@Trial2026 (free-trial account)')
