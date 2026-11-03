"""Free-trial rules: a user without a subscription may explore each experiment once.

A visit starts when the experiment is opened and stays valid (reloads are fine) until the user
returns to the lab index or a dashboard, opens a different experiment, signs out, or
TRIAL_VISIT_MAX_HOURS pass. After that the experiment shows 'Subscription only'.
"""
from django.conf import settings
from django.utils import timezone

from .models import TrialVisit

AVAILABLE, OPEN, USED = 'available', 'open', 'used'


def _expired(v):
    return timezone.now() - v.started_at > timezone.timedelta(hours=settings.TRIAL_VISIT_MAX_HOURS)


def consume_open(user, reason, except_experiment=None):
    if not user.is_authenticated or user.has_full_access:
        return 0
    qs = TrialVisit.objects.filter(user=user, consumed_at__isnull=True)
    if except_experiment is not None:
        qs = qs.exclude(experiment=except_experiment)
    return qs.update(consumed_at=timezone.now(), consumed_by=reason)


def states(user):
    """{experiment_id: state} for a trial user."""
    out = {}
    for v in TrialVisit.objects.filter(user=user):
        if v.consumed_at is None and _expired(v):
            v.consumed_at, v.consumed_by = timezone.now(), 'expired'
            v.save(update_fields=['consumed_at', 'consumed_by'])
        out[v.experiment_id] = OPEN if v.consumed_at is None else USED
    return out


def enter(user, experiment):
    """Try to open an experiment for a trial user. Returns (allowed, visit)."""
    v = TrialVisit.objects.filter(user=user, experiment=experiment).first()
    if v is None:
        consume_open(user, 'other_module', except_experiment=experiment)
        return True, TrialVisit.objects.create(user=user, experiment=experiment)
    if v.consumed_at is None and _expired(v):
        v.consumed_at, v.consumed_by = timezone.now(), 'expired'
        v.save(update_fields=['consumed_at', 'consumed_by'])
    if v.consumed_at is None:
        consume_open(user, 'other_module', except_experiment=experiment)
        return True, v
    return False, v
