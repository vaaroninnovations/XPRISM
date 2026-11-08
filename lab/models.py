import secrets
import string

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Role(models.TextChoices):
    SUPERADMIN = 'superadmin', 'Super Admin'
    COLLEGE_ADMIN = 'college_admin', 'College Admin'
    FACULTY = 'faculty', 'Faculty'
    LAB_ASSISTANT = 'lab_assistant', 'Lab Assistant'
    STUDENT = 'student', 'Student'


STAFF_ROLES = (Role.COLLEGE_ADMIN, Role.FACULTY, Role.LAB_ASSISTANT)


class College(models.Model):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=20, unique=True, help_text='Short code used as username prefix, e.g. "rgcp"')
    location_text = models.CharField('Location line in header', max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    grievance_officer = models.CharField(max_length=120, blank=True)
    grievance_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    subscription_active = models.BooleanField('Subscription active', default=True, help_text='Users of a subscribed college get unlimited access to all enabled experiments')
    subscription_until = models.DateField('Subscription valid until', null=True, blank=True, help_text='Leave blank for no end date')
    disabled_experiments = models.ManyToManyField('Experiment', blank=True, related_name='disabled_in')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_subscribed(self):
        return self.is_active and self.subscription_active and (self.subscription_until is None or self.subscription_until >= timezone.localdate())


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    college = models.ForeignKey(College, null=True, blank=True, on_delete=models.PROTECT, related_name='users')
    roll_no = models.CharField('Roll / enrolment no.', max_length=40, blank=True)
    must_change_password = models.BooleanField(default=False)
    consent_version = models.CharField(max_length=20, blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    failed_logins = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    anonymised = models.BooleanField(default=False)
    # free trial / individual subscription
    is_trial_account = models.BooleanField(default=False, help_text='Self-registered free-trial user (not enrolled through a college)')
    institution = models.CharField(max_length=200, blank=True)
    occupation = models.CharField(max_length=40, blank=True)
    subscribed_until = models.DateField('Individual subscription until', null=True, blank=True)
    ethics_version = models.CharField(max_length=20, blank=True)
    ethics_at = models.DateTimeField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def is_role(self, *roles):
        return self.is_authenticated and (self.role in roles)

    @property
    def is_platform_admin(self):
        return self.role == Role.SUPERADMIN or self.is_superuser

    @property
    def is_shared_demo(self):
        """A public login printed in adverts: AccountGateMiddleware limits what it can change."""
        return self.username in settings.SHARED_DEMO_USERNAMES

    @property
    def has_full_access(self):
        """Unlimited use of experiments: platform admins, members of a subscribed college, or an individual subscription."""
        if self.is_platform_admin:
            return True
        if self.subscribed_until and self.subscribed_until >= timezone.localdate():
            return True
        return bool(self.college and self.college.is_subscribed)

    def save(self, *args, **kwargs):
        if self.is_superuser and self.role != Role.SUPERADMIN:
            self.role = Role.SUPERADMIN
        self.is_staff = self.role == Role.SUPERADMIN or self.is_superuser   # Django /admin/ only for platform admins
        super().save(*args, **kwargs)


CATEGORIES = [('In-vivo', 'In-vivo simulations', 'Behavioural, anticonvulsant, analgesic, anti-inflammatory, cardiovascular and gastrointestinal studies'),
              ('Isolated tissue', 'Isolated tissue experiments', 'Frog and rat preparations, kymograph recording and dose–response curves'),
              ('Bioassay', 'Bioassay experiments', 'Histamine bioassays, three-point and four-point designs, and pA2 estimation'),
              ('Molecular biology', 'Molecular biology experiments', 'RNA and DNA isolation, cDNA synthesis, PCR analysis and gel electrophoresis'),
              ('Cell culture', 'Cell culture experiments', 'Cultured cell handling, 96-well plate assays, cell viability and IC50'),
              ('Neurobehavioural', 'Neurobehavioural experiments', 'Learning, memory, anxiety, avoidance and antidepressant tests: Y-maze, radial arm maze, light-dark box, water maze, Barnes maze, pole climbing and forced swim'),
              ('Ethics and clinical', 'Ethics, pharmacovigilance and clinical trials', 'Animal ethics review, adverse drug reaction reporting and clinical trial design'),
              ('Biochemical assays', 'Biochemical and immunoassays', 'Serum biochemistry, ELISA and oxidative stress markers')]


LEVELS = [('Basic', 'B.Pharm practicals: core techniques, screening methods, isolated tissues, bioassays and serum biochemistry'),
          ('Advanced', 'M.Pharm screening: neurobehavioural models of learning, memory, avoidance and depression, and animal ethics review'),
          ('Research', 'Research methods: molecular biology, cell-based and biochemical assays, pharmacovigilance and clinical trial design')]


class Experiment(models.Model):
    no = models.PositiveSmallIntegerField(unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=40)
    level = models.CharField(max_length=20, default='Basic')
    description = models.TextField(blank=True)
    is_demo = models.BooleanField('Open to visitors without login', default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['no']

    def __str__(self):
        return f'Exp {self.no:02d}: {self.title}'

    @property
    def url(self):
        return f'/experiments/{self.slug}.html'

    def enabled_for(self, college):
        return self.is_active and (college is None or not college.disabled_experiments.filter(pk=self.pk).exists())


def new_class_code():
    alphabet = string.ascii_uppercase.replace('O', '').replace('I', '') + '23456789'
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        if not Batch.objects.filter(class_code=code).exists():
            return code


class Batch(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='batches')
    name = models.CharField(max_length=120, help_text='e.g. "B.Pharm Section A"')
    academic_year = models.CharField(max_length=20, default='2026-27')
    faculty = models.ManyToManyField(User, related_name='teaching_batches', blank=True)
    class_code = models.CharField(max_length=12, unique=True, blank=True)
    join_enabled = models.BooleanField('Students may join with the class code', default=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'batches'

    def __str__(self):
        return f'{self.name} ({self.academic_year})'

    def save(self, *args, **kwargs):
        if not self.class_code:
            self.class_code = new_class_code()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('batch_detail', args=[self.pk])


class Enrollment(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    joined_at = models.DateTimeField(auto_now_add=True)
    via = models.CharField(max_length=20, default='faculty')   # faculty | csv | class_code

    class Meta:
        unique_together = ('batch', 'student')


class Assignment(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='assignments')
    experiment = models.ForeignKey(Experiment, on_delete=models.PROTECT, related_name='assignments')
    instructions = models.TextField(blank=True)
    opens_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField()
    max_marks = models.DecimalField(max_digits=5, decimal_places=1, default=10)
    exam_mode = models.BooleanField(default=False, help_text='Hides reference datasets, auto-run and skip buttons; enforces time limit')
    time_limit_min = models.PositiveIntegerField('Time limit (minutes)', null=True, blank=True)
    max_attempts = models.PositiveSmallIntegerField(default=2)
    allow_late = models.BooleanField('Accept late submissions', default=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_at']

    def __str__(self):
        return f'{self.experiment} → {self.batch}'

    @property
    def is_open(self):
        now = timezone.now()
        return self.opens_at <= now and (now <= self.due_at or self.allow_late)

    @property
    def is_overdue(self):
        return timezone.now() > self.due_at

    def get_absolute_url(self):
        return reverse('assignment_detail', args=[self.pk])

    def launch_url(self):
        return f'{self.experiment.url}?a={self.pk}'


class Attempt(models.Model):
    STARTED, SUBMITTED, GRADED = 'started', 'submitted', 'graded'
    STATUS = [(STARTED, 'In progress'), (SUBMITTED, 'Submitted'), (GRADED, 'Graded')]
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attempts')
    status = models.CharField(max_length=12, choices=STATUS, default=STARTED)
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    viva_score = models.PositiveSmallIntegerField(null=True, blank=True)
    viva_total = models.PositiveSmallIntegerField(null=True, blank=True)
    answer_given = models.CharField(max_length=120, blank=True)
    answer_true = models.CharField(max_length=120, blank=True)
    answer_ok = models.BooleanField(null=True)
    completion = models.BooleanField(default=False)
    auto_score = models.FloatField(null=True, blank=True)        # 0-100
    manual_marks = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    graded_at = models.DateTimeField(null=True, blank=True)
    is_late = models.BooleanField(default=False)
    timed_out = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    @property
    def deadline(self):
        lim = self.assignment.time_limit_min
        return self.started_at + timezone.timedelta(minutes=lim) if (self.assignment.exam_mode and lim) else None

    @property
    def duration_min(self):
        end = self.submitted_at or timezone.now()
        return round((end - self.started_at).total_seconds() / 60, 1)

    def compute_auto_score(self):
        parts = []  # (weight, fraction)
        if self.viva_total:
            parts.append((40, self.viva_score / self.viva_total))
        if self.answer_ok is not None:
            parts.append((30, 1.0 if self.answer_ok else 0.0))
        parts.append((30, 1.0 if self.completion else 0.0))
        w = sum(p[0] for p in parts)
        self.auto_score = round(sum(p[0] * p[1] for p in parts) / w * 100, 1)
        return self.auto_score

    @property
    def final_marks(self):
        if self.manual_marks is not None:
            return float(self.manual_marks)
        if self.auto_score is None:
            return None
        return round(self.auto_score / 100 * float(self.assignment.max_marks), 1)


class AuditLog(models.Model):
    at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    college = models.ForeignKey(College, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=200, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-at']


class ConsentRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consents')
    policy_version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)


class DataRequest(models.Model):
    EXPORT, DELETION, CORRECTION = 'export', 'deletion', 'correction'
    KINDS = [(EXPORT, 'Data export'), (DELETION, 'Account deletion'), (CORRECTION, 'Correction')]
    OPEN, DONE, REJECTED = 'open', 'done', 'rejected'
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='data_requests')
    username_snapshot = models.CharField(max_length=150, blank=True)
    college = models.ForeignKey(College, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=12, choices=KINDS)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=[(OPEN, 'Open'), (DONE, 'Completed'), (REJECTED, 'Rejected')], default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']


class FreeYearApplication(models.Model):
    """A request for one free year of access, made from the public pop-up and decided by a super admin."""
    INDIVIDUAL, COLLEGE = 'individual', 'college'
    KINDS = [(COLLEGE, 'My college'), (INDIVIDUAL, 'Myself')]
    OCCUPATIONS = [('faculty', 'Faculty / teacher'), ('student', 'Student'), ('researcher', 'Researcher'), ('other', 'Other')]
    PENDING, APPROVED, REJECTED = 'pending', 'approved', 'rejected'
    kind = models.CharField('Applying for', max_length=12, choices=KINDS, default=COLLEGE)
    name = models.CharField('Full name', max_length=120)
    email = models.EmailField('E-mail', max_length=150)
    phone = models.CharField('Phone', max_length=20, blank=True)
    institution = models.CharField('College / institution', max_length=200)
    occupation = models.CharField('I am a', max_length=40, choices=OCCUPATIONS, default='faculty')
    message = models.TextField(max_length=1000, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='free_year_applications')
    status = models.CharField(max_length=10, choices=[(PENDING, 'Pending'), (APPROVED, 'Approved'), (REJECTED, 'Declined')], default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    awarded_until = models.DateField(null=True, blank=True)
    awarded_college = models.ForeignKey(College, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} <{self.email}> ({self.status})'


def new_invitation_token():
    return secrets.token_urlsafe(24)


class FreeYearInvitation(models.Model):
    """An e-mail inviting a college to apply for the free year. Each address is invited once, and can opt out."""
    QUEUED, SENT, FAILED = 'queued', 'sent', 'failed'
    email = models.EmailField(unique=True)
    token = models.CharField(max_length=40, unique=True, default=new_invitation_token, editable=False)    # for the opt-out link
    status = models.CharField(max_length=10, choices=[(QUEUED, 'Sending'), (SENT, 'Sent'), (FAILED, 'Failed')], default=QUEUED)
    invited_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    opted_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.email} ({self.status})'

    @property
    def can_retry(self):
        """Failed, or still queued after an hour (the server restarted while sending). A recent queued one is on its way: retrying would send it twice."""
        if self.opted_out_at or self.status == self.SENT:
            return False
        return self.status == self.FAILED or timezone.now() - self.created_at > timezone.timedelta(hours=1)


class TrialVisit(models.Model):
    """One free exploration of an experiment by a user without a subscription."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trial_visits')
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='trial_visits')
    started_at = models.DateTimeField(default=timezone.now)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.CharField(max_length=30, blank=True)   # index | dashboard | other_module | expired | logout

    class Meta:
        unique_together = ('user', 'experiment')
        ordering = ['-started_at']
