import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import access
from .forms import ConsentForm, DataRequestForm, EthicsAgreementForm, SignupForm, TrialSignupForm, INPUT
from .models import Attempt, ConsentRecord, DataRequest, Enrollment, Role, User
from .permissions import audit, client_ip


def _safe_next(request, default):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return default


def home(request):
    """Send each role to its own start page."""
    u = request.user
    if not u.is_authenticated:
        return redirect('landing')
    access.consume_open(u, 'dashboard')
    if u.is_trial_account and not u.has_full_access:
        return redirect('landing')
    if u.is_platform_admin:
        return redirect('platform_dashboard')
    return redirect({Role.COLLEGE_ADMIN: 'college_dashboard', Role.FACULTY: 'staff_dashboard', Role.LAB_ASSISTANT: 'staff_dashboard'}.get(u.role, 'student_dashboard'))


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request, '/home/'))
    form = AuthenticationForm(request, data=request.POST or None)
    for f in form.fields.values():
        f.widget.attrs['class'] = INPUT
    error = None
    if request.method == 'POST':
        ip = client_ip(request)
        ip_key = f'login-ip:{ip}'
        ip_fails = cache.get(ip_key, 0)
        uname = request.POST.get('username', '').strip()
        target = User.objects.filter(username__iexact=uname).first()
        now = timezone.now()
        if ip_fails >= 20:
            error = 'Too many failed sign-in attempts from this network. Please wait 15 minutes.'
        elif target and target.locked_until and target.locked_until > now:
            mins = int((target.locked_until - now).total_seconds() // 60) + 1
            error = f'This account is temporarily locked after repeated failed sign-ins. Try again in {mins} minute(s), or ask your faculty to reset your password.'
        elif form.is_valid():
            user = form.get_user()
            if user.college and not user.college.is_active and not user.is_platform_admin:
                error = 'Your college account is currently inactive. Please contact your college.'
            else:
                user.failed_logins, user.locked_until = 0, None
                user.save(update_fields=['failed_logins', 'locked_until'])
                login(request, user)
                audit(request, 'login', user.username)
                return redirect(_safe_next(request, '/home/'))
        else:
            cache.set(ip_key, ip_fails + 1, 15 * 60)
            if target:
                target.failed_logins += 1
                if target.failed_logins >= settings.LOGIN_MAX_FAILURES:
                    target.locked_until = now + timezone.timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
                    target.failed_logins = 0
                    audit(request, 'account_locked', target.username, college=target.college)
                target.save(update_fields=['failed_logins', 'locked_until'])
            error = 'Incorrect username or password.'
    return render(request, 'registration/login.html', {'form': form, 'error': error, 'next': request.GET.get('next', '')})


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignupForm(request.POST or None, initial={'class_code': request.GET.get('code', '')})
    if request.method == 'POST' and form.is_valid():
        cd, batch = form.cleaned_data, form.batch
        with transaction.atomic():
            u = User(username=form.username, first_name=cd['first_name'], last_name=cd.get('last_name', ''), email=cd.get('email', ''),
                     role=Role.STUDENT, college=batch.college, roll_no=cd['roll_no'], consent_version=settings.POLICY_VERSION, consent_at=timezone.now())
            u.set_password(cd['password1'])
            u.save()
            ConsentRecord.objects.create(user=u, policy_version=settings.POLICY_VERSION, ip=client_ip(request))
            Enrollment.objects.create(batch=batch, student=u, via='class_code')
        login(request, u, backend='django.contrib.auth.backends.ModelBackend')
        audit(request, 'signup', u.username, college=batch.college, batch=batch.pk)
        messages.success(request, f'Welcome! Your username is {u.username}. You have joined {batch.name}.')
        return redirect('student_dashboard')
    return render(request, 'registration/signup.html', {'form': form})


def trial_signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = TrialSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        u = User(username=cd['email'], email=cd['email'], first_name=cd['first_name'], last_name=cd.get('last_name', ''), role=Role.STUDENT,
                 is_trial_account=True, institution=cd.get('institution', ''), occupation=cd['occupation'],
                 consent_version=settings.POLICY_VERSION, consent_at=timezone.now())
        u.set_password(cd['password1'])
        u.save()
        ConsentRecord.objects.create(user=u, policy_version=settings.POLICY_VERSION, ip=client_ip(request))
        login(request, u, backend='django.contrib.auth.backends.ModelBackend')
        audit(request, 'trial_signup', u.username, occupation=u.occupation)
        return redirect('landing')
    return render(request, 'registration/trial_signup.html', {'form': form})


@login_required
@require_POST
def ethics_agreement(request):
    u = request.user
    form = EthicsAgreementForm(request.POST, trial=not u.has_full_access)
    if not form.is_valid():
        messages.error(request, 'Please tick the box(es) to accept the trial rules and the ethical-use agreement.')
        return redirect(f"/?agree=1&next={request.POST.get('next', '')}")
    u.ethics_version, u.ethics_at = settings.ETHICS_VERSION, timezone.now()
    u.save(update_fields=['ethics_version', 'ethics_at'])
    ConsentRecord.objects.create(user=u, policy_version=f'ethics-{settings.ETHICS_VERSION}', ip=client_ip(request))
    audit(request, 'ethics_agreement', settings.ETHICS_VERSION, trial=not u.has_full_access)
    return redirect(_safe_next(request, '/'))


@login_required
def consent(request):
    form = ConsentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        u = request.user
        u.consent_version, u.consent_at = settings.POLICY_VERSION, timezone.now()
        u.save(update_fields=['consent_version', 'consent_at'])
        ConsentRecord.objects.create(user=u, policy_version=settings.POLICY_VERSION, ip=client_ip(request))
        audit(request, 'consent', settings.POLICY_VERSION)
        return redirect(_safe_next(request, '/home/'))
    return render(request, 'registration/consent.html', {'form': form, 'next': request.GET.get('next', '')})


@login_required
def force_password(request):
    form = SetPasswordForm(request.user, request.POST or None)
    for f in form.fields.values():
        f.widget.attrs['class'] = INPUT
    if request.method == 'POST' and form.is_valid():
        u = form.save()
        u.must_change_password = False
        u.save(update_fields=['must_change_password'])
        update_session_auth_hash(request, u)
        audit(request, 'password_changed', u.username)
        messages.success(request, 'Password updated.')
        return redirect(_safe_next(request, '/home/'))
    return render(request, 'registration/force_password.html', {'form': form, 'forced': request.user.must_change_password, 'next': request.GET.get('next', '')})


# ------------------------------------------------------------------ data-protection rights
def _export(u):
    return {
        'exported_at': timezone.now().isoformat(),
        'account': {'username': u.username, 'first_name': u.first_name, 'last_name': u.last_name, 'email': u.email,
                    'role': u.role, 'college': u.college.name if u.college else None, 'roll_no': u.roll_no,
                    'date_joined': u.date_joined.isoformat(), 'last_login': u.last_login.isoformat() if u.last_login else None},
        'consents': [{'policy_version': c.policy_version, 'accepted_at': c.accepted_at.isoformat()} for c in u.consents.all()],
        'batches': [{'batch': e.batch.name, 'academic_year': e.batch.academic_year, 'joined_at': e.joined_at.isoformat()} for e in u.enrollments.select_related('batch')],
        'attempts': [{'experiment': str(a.assignment.experiment), 'status': a.status, 'started_at': a.started_at.isoformat(),
                      'submitted_at': a.submitted_at.isoformat() if a.submitted_at else None, 'auto_score': a.auto_score,
                      'marks': a.final_marks, 'max_marks': float(a.assignment.max_marks), 'feedback': a.feedback, 'submission': a.payload}
                     for a in u.attempts.select_related('assignment__experiment')],
    }


@login_required
def my_data(request):
    u = request.user
    if request.GET.get('download') == '1':
        DataRequest.objects.create(user=u, username_snapshot=u.username, college=u.college, kind=DataRequest.EXPORT, status=DataRequest.DONE, resolved_at=timezone.now(), resolution_note='Self-service download')
        audit(request, 'data_export', u.username)
        resp = HttpResponse(json.dumps(_export(u), indent=2, default=str), content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="xprism-my-data-{u.username}.json"'
        return resp
    form = DataRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if u.data_requests.filter(status=DataRequest.OPEN, kind=form.cleaned_data['kind']).exists():
            messages.info(request, 'You already have an open request of this type.')
        else:
            DataRequest.objects.create(user=u, username_snapshot=u.username, college=u.college, kind=form.cleaned_data['kind'], message=form.cleaned_data['message'])
            audit(request, 'data_request', form.cleaned_data['kind'])
            messages.success(request, 'Request received. Your college admin will respond within 30 days.')
        return redirect('my_data')
    return render(request, 'lab/my_data.html', {'form': form, 'requests': u.data_requests.all()[:20], 'n_attempts': u.attempts.count()})


def anonymise_user(user):
    """Erase personal identifiers but keep de-identified academic records (marks) for the college's statistics."""
    user.first_name, user.last_name, user.email, user.roll_no = 'Deleted', 'user', '', ''
    user.username = f'deleted-{user.pk}'
    user.is_active, user.anonymised = False, True
    user.set_unusable_password()
    user.save()
    Attempt.objects.filter(student=user).update(payload={}, feedback='')
    Enrollment.objects.filter(student=user).delete()
