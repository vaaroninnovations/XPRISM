"""Role checks and data scoping. Every view that touches college data goes through these helpers."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Assignment, Attempt, Batch, Role


def role_required(*roles):
    """Allow only the given roles (super admins always pass)."""
    def deco(view):
        @login_required
        @wraps(view)
        def wrapped(request, *a, **kw):
            u = request.user
            if not (u.is_platform_admin or u.role in roles):
                raise PermissionDenied
            return view(request, *a, **kw)
        return wrapped
    return deco


def batches_for(user):
    """Batches the user may see."""
    qs = Batch.objects.select_related('college')
    if user.is_platform_admin:
        return qs
    if user.role in (Role.COLLEGE_ADMIN, Role.LAB_ASSISTANT):
        return qs.filter(college=user.college)
    if user.role == Role.FACULTY:
        return qs.filter(college=user.college, faculty=user)
    if user.role == Role.STUDENT:
        return qs.filter(enrollments__student=user)
    return qs.none()


def can_manage_batch(user, batch):
    """Edit batch, create assignments, grade: owning faculty, college admin of that college, platform admin."""
    if user.is_platform_admin:
        return True
    if user.role == Role.COLLEGE_ADMIN and batch.college_id == user.college_id:
        return True
    return user.role == Role.FACULTY and batch.faculty.filter(pk=user.pk).exists()


def can_grade(user, batch):
    if user.is_platform_admin:
        return True
    return user.role == Role.FACULTY and batch.college_id == user.college_id and batch.faculty.filter(pk=user.pk).exists()


def can_enrol(user, batch):
    return can_manage_batch(user, batch) or (user.role == Role.LAB_ASSISTANT and batch.college_id == user.college_id)


def get_batch_or_403(user, pk):
    batch = get_object_or_404(Batch, pk=pk)
    if not batches_for(user).filter(pk=batch.pk).exists():
        raise PermissionDenied
    return batch


def get_assignment_or_403(user, pk):
    a = get_object_or_404(Assignment.objects.select_related('batch', 'experiment'), pk=pk)
    get_batch_or_403(user, a.batch_id)
    return a


def get_attempt_or_403(user, pk):
    at = get_object_or_404(Attempt.objects.select_related('assignment__batch', 'assignment__experiment', 'student'), pk=pk)
    if user.role == Role.STUDENT:
        if at.student_id != user.pk:
            raise PermissionDenied
    else:
        get_batch_or_403(user, at.assignment.batch_id)
    return at


def client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR')) or None


def audit(request, action, target='', college=None, **detail):
    from .models import AuditLog
    u = request.user if request.user.is_authenticated else None
    AuditLog.objects.create(actor=u, college=college or (u.college if u else None), action=action, target=str(target)[:200], detail=detail, ip=client_ip(request))
