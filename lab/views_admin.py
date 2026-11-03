from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BrandingForm, CollegeCreateForm, CollegeForm, StaffUserForm, make_username, temp_password
import datetime

from .models import Attempt, AuditLog, Batch, College, DataRequest, Experiment, Role, TrialVisit, User
from .permissions import audit, role_required
from .views_auth import anonymise_user


def _college(request):
    """College admins act on their own college; platform admins may pass ?college=<id>."""
    u = request.user
    if u.is_platform_admin:
        cid = request.GET.get('college') or request.POST.get('college')
        return get_object_or_404(College, pk=cid) if cid else None
    return u.college


@role_required(Role.COLLEGE_ADMIN)
def college_dashboard(request):
    c = _college(request)
    if c is None:
        return redirect('platform_dashboard')
    users = User.objects.filter(college=c)
    stats = {
        'students': users.filter(role=Role.STUDENT, is_active=True).count(),
        'faculty': users.filter(role=Role.FACULTY, is_active=True).count(),
        'assistants': users.filter(role=Role.LAB_ASSISTANT, is_active=True).count(),
        'batches': Batch.objects.filter(college=c, archived=False).count(),
        'submissions': Attempt.objects.filter(assignment__batch__college=c).exclude(status=Attempt.STARTED).count(),
        'to_grade': Attempt.objects.filter(assignment__batch__college=c, status=Attempt.SUBMITTED).count(),
        'experiments': Experiment.objects.filter(is_active=True).exclude(pk__in=c.disabled_experiments.values('pk')).count(),
    }
    recent = AuditLog.objects.filter(college=c).select_related('actor')[:10]
    return render(request, 'lab/college_dashboard.html', {'c': c, 'stats': stats, 'recent': recent})


@role_required(Role.COLLEGE_ADMIN)
def staff_users(request):
    c = _college(request)
    if c is None:
        raise PermissionDenied
    form = StaffUserForm(request.POST or None, college=c)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        pw = temp_password()
        u = User(username=form.username, first_name=cd['first_name'], last_name=cd['last_name'], email=cd['email'], role=cd['role'], college=c, must_change_password=True)
        u.set_password(pw)
        u.save()
        audit(request, 'staff_created', u.username, college=c, role=u.role)
        messages.success(request, f'{u.get_role_display()} account created. Username: {u.username} • Temporary password: {pw} (shown once; must be changed at first sign-in)')
        return redirect(request.get_full_path())
    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', 'staff')
    users = User.objects.filter(college=c, anonymised=False)
    users = users.filter(role__in=[Role.FACULTY, Role.LAB_ASSISTANT, Role.COLLEGE_ADMIN]) if role == 'staff' else users.filter(role=Role.STUDENT)
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(roll_no__icontains=q))
    page = Paginator(users.order_by('role', 'first_name'), 50).get_page(request.GET.get('page'))
    return render(request, 'lab/staff_users.html', {'c': c, 'form': form, 'page': page, 'q': q, 'role': role, 'now': timezone.now()})


@require_POST
@role_required(Role.COLLEGE_ADMIN)
def user_action(request, user_id, action):
    c = _college(request)
    target = get_object_or_404(User, pk=user_id)
    if not request.user.is_platform_admin and target.college_id != c.pk:
        raise PermissionDenied
    if target.pk == request.user.pk and action in ('toggle', 'role'):
        messages.error(request, 'You cannot change your own account here.')
        return redirect(request.META.get('HTTP_REFERER', '/college/users/'))
    if target.is_platform_admin:
        raise PermissionDenied
    if action == 'toggle':
        target.is_active = not target.is_active; target.save()
        messages.success(request, f'{target.username} {"activated" if target.is_active else "deactivated"}.')
    elif action == 'reset':
        pw = temp_password(); target.set_password(pw); target.must_change_password = True; target.locked_until = None; target.failed_logins = 0; target.save()
        messages.success(request, f'Temporary password for {target.username}: {pw}')
    elif action == 'role':
        new = request.POST.get('role')
        if new in (Role.FACULTY, Role.LAB_ASSISTANT, Role.COLLEGE_ADMIN) and target.role != Role.STUDENT:
            target.role = new; target.save(); messages.success(request, f'{target.username} is now {target.get_role_display()}.')
    audit(request, f'user_{action}', target.username, college=target.college)
    return redirect(request.META.get('HTTP_REFERER', '/college/users/'))


@role_required(Role.COLLEGE_ADMIN)
def college_experiments(request):
    c = _college(request)
    if c is None:
        return redirect('platform_experiments')
    if request.method == 'POST':
        enabled = set(int(x) for x in request.POST.getlist('enabled'))
        all_ids = set(Experiment.objects.values_list('pk', flat=True))
        c.disabled_experiments.set(all_ids - enabled)
        audit(request, 'experiments_updated', c, college=c, disabled=sorted(all_ids - enabled))
        messages.success(request, f'{len(enabled)} experiments enabled for {c.name}.')
        return redirect('college_experiments')
    disabled = set(c.disabled_experiments.values_list('pk', flat=True))
    exps = Experiment.objects.filter(is_active=True)
    return render(request, 'lab/college_experiments.html', {'c': c, 'exps': exps, 'disabled': disabled})


@role_required(Role.COLLEGE_ADMIN)
def college_settings(request):
    c = _college(request)
    if c is None:
        raise PermissionDenied
    form = BrandingForm(request.POST or None, instance=c)
    if request.method == 'POST' and form.is_valid():
        form.save()
        audit(request, 'college_settings', c, college=c)
        messages.success(request, 'College details saved.')
        return redirect('college_settings')
    return render(request, 'lab/form_page.html', {'form': form, 'title': f'College details • {c.name}', 'back': '/college/',
                                                  'help': 'The location line appears in the header of every page your users see. The grievance officer is shown to your students in the Privacy Policy.'})


@role_required(Role.COLLEGE_ADMIN)
def audit_log(request):
    qs = AuditLog.objects.select_related('actor', 'college')
    if not request.user.is_platform_admin:
        qs = qs.filter(college=request.user.college)
    act = request.GET.get('action', '').strip()
    if act:
        qs = qs.filter(action__icontains=act)
    page = Paginator(qs, 50).get_page(request.GET.get('page'))
    return render(request, 'lab/audit_log.html', {'page': page, 'action': act})


@role_required(Role.COLLEGE_ADMIN)
def data_requests(request):
    qs = DataRequest.objects.select_related('user', 'college', 'resolved_by')
    if not request.user.is_platform_admin:
        qs = qs.filter(college=request.user.college)
    if request.method == 'POST':
        r = get_object_or_404(qs, pk=request.POST.get('id'))
        decision, note = request.POST.get('decision'), request.POST.get('note', '').strip()
        if r.status != DataRequest.OPEN:
            messages.error(request, 'This request is already closed.')
        elif decision == 'approve':
            with transaction.atomic():
                if r.kind == DataRequest.DELETION and r.user and not r.user.is_platform_admin:
                    anonymise_user(r.user)
                r.status, r.resolution_note = DataRequest.DONE, note or ('Personal data erased; de-identified marks retained.' if r.kind == DataRequest.DELETION else 'Completed')
                r.resolved_by, r.resolved_at = request.user, timezone.now()
                r.save()
            audit(request, 'data_request_done', r.username_snapshot, college=r.college, kind=r.kind)
            messages.success(request, f'Request #{r.pk} completed.')
        elif decision == 'reject':
            r.status, r.resolution_note, r.resolved_by, r.resolved_at = DataRequest.REJECTED, note or 'Rejected', request.user, timezone.now()
            r.save()
            audit(request, 'data_request_rejected', r.username_snapshot, college=r.college, kind=r.kind)
            messages.success(request, f'Request #{r.pk} rejected.')
        return redirect('data_requests')
    return render(request, 'lab/data_requests.html', {'open': qs.filter(status=DataRequest.OPEN).exclude(kind=DataRequest.EXPORT), 'closed': qs.exclude(status=DataRequest.OPEN)[:50]})


# ------------------------------------------------------------------ platform (super admin)
def _platform(view):
    return role_required(Role.SUPERADMIN)(view)


@_platform
def platform_dashboard(request):
    colleges = College.objects.annotate(
        n_students=Count('users', filter=Q(users__role=Role.STUDENT, users__is_active=True), distinct=True),
        n_staff=Count('users', filter=Q(users__role__in=[Role.FACULTY, Role.LAB_ASSISTANT, Role.COLLEGE_ADMIN]), distinct=True),
        n_batches=Count('batches', distinct=True))
    stats = {'colleges': colleges.count(), 'users': User.objects.filter(is_active=True).count(),
             'submissions': Attempt.objects.exclude(status=Attempt.STARTED).count(), 'experiments': Experiment.objects.filter(is_active=True).count(),
             'open_requests': DataRequest.objects.filter(status=DataRequest.OPEN).exclude(kind=DataRequest.EXPORT).count(),
             'trial_users': User.objects.filter(is_trial_account=True, is_active=True).count(),
             'trial_visits': TrialVisit.objects.count()}
    return render(request, 'lab/platform_dashboard.html', {'colleges': colleges, 'stats': stats})


@_platform
def college_list(request):
    return render(request, 'lab/college_list.html', {'colleges': College.objects.annotate(n_users=Count('users')).order_by('name')})


@_platform
def college_form(request, pk=None):
    c = get_object_or_404(College, pk=pk) if pk else None
    form = (CollegeForm if c else CollegeCreateForm)(request.POST or None, instance=c)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            college = form.save()
            if not c:
                cd = form.cleaned_data
                pw = temp_password()
                uname = make_username(college, 'admin')
                admin = User(username=uname, first_name=cd['admin_first_name'], last_name=cd['admin_last_name'], email=cd['admin_email'],
                             role=Role.COLLEGE_ADMIN, college=college, must_change_password=True)
                admin.set_password(pw)
                admin.save()
                messages.success(request, f'College created. College admin username: {uname} • Temporary password: {pw} (shown once)')
        audit(request, 'college_saved', college, college=college)
        if c:
            messages.success(request, 'College saved.')
        return redirect('college_list')
    return render(request, 'lab/form_page.html', {'form': form, 'title': f'Edit {c.name}' if c else 'New college', 'back': '/platform/colleges/',
                                                  'help': None if c else 'A College Admin account is created with the college. Usernames in this college start with its code.'})


@_platform
def platform_experiments(request):
    if request.method == 'POST':
        for e in Experiment.objects.all():
            e.is_active = f'active_{e.pk}' in request.POST
            e.save(update_fields=['is_active'])
        audit(request, 'catalogue_updated', 'experiments')
        messages.success(request, 'Experiment catalogue updated.')
        return redirect('platform_experiments')
    return render(request, 'lab/platform_experiments.html', {'exps': Experiment.objects.all()})


@_platform
def trial_users(request):
    """Free-trial accounts: usage, and granting / revoking individual subscriptions."""
    if request.method == 'POST':
        u = get_object_or_404(User, pk=request.POST.get('user'), is_trial_account=True)
        act = request.POST.get('action')
        if act == 'grant':
            try:
                until = datetime.date.fromisoformat(request.POST.get('until', ''))
            except ValueError:
                messages.error(request, 'Choose a valid end date.')
                return redirect('trial_users')
            u.subscribed_until = until; u.save(update_fields=['subscribed_until'])
            messages.success(request, f'{u.username} subscribed until {until:%d %b %Y}.')
        elif act == 'revoke':
            u.subscribed_until = None; u.save(update_fields=['subscribed_until'])
            messages.success(request, f'Subscription removed for {u.username}.')
        elif act == 'reset':
            n = TrialVisit.objects.filter(user=u).delete()[0]
            messages.success(request, f'Free-trial visits reset for {u.username} ({n} cleared).')
        audit(request, f'trial_{act}', u.username, until=request.POST.get('until', ''))
        return redirect(request.get_full_path())
    q = request.GET.get('q', '').strip()
    users = User.objects.filter(is_trial_account=True).annotate(
        n_used=Count('trial_visits', filter=Q(trial_visits__consumed_at__isnull=False), distinct=True),
        n_visits=Count('trial_visits', distinct=True)).order_by('-date_joined')
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(institution__icontains=q))
    page = Paginator(users, 50).get_page(request.GET.get('page'))
    return render(request, 'lab/trial_users.html', {'page': page, 'q': q, 'today': timezone.localdate(), 'n_exp': Experiment.objects.filter(is_active=True).count()})
