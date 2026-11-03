"""One free year of access, awarded by a super admin from a FreeYearApplication.

An individual gets User.subscribed_until on their account (created if they have none). A college
gets College.subscription_until, on an existing college or on a new one with its College Admin.
An award never shortens access: it runs for a year from the later of today and the current end date.
"""
import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.text import slugify

from .forms import make_username, temp_password
from .models import College, FreeYearApplication, Role, User


def parse_addresses(text):
    """Pasted text, separated by commas, semicolons, spaces or new lines, as (valid addresses without repeats, invalid entries)."""
    valid, invalid = {}, []
    for entry in re.split(r'[\s,;]+', text):
        entry = entry.strip('<>"\'').lower()
        if not entry:
            continue
        try:
            validate_email(entry)
            valid[entry] = True
        except ValidationError:
            invalid.append(entry)
    return list(valid), invalid


def one_year_after(day):
    try:
        return day.replace(year=day.year + 1)
    except ValueError:      # 29 February
        return day.replace(year=day.year + 1, day=28)


def _award_end(current_end):
    today = timezone.localdate()
    return one_year_after(max(today, current_end) if current_end else today)


def find_account(app):
    if app.user_id:
        return app.user
    accounts = User.objects.filter(anonymised=False)
    return (accounts.filter(username__iexact=app.email).first()
            or accounts.filter(email__iexact=app.email).order_by('-is_trial_account', 'pk').first())


def _new_account(app, username, **fields):
    first, _, last = app.name.partition(' ')
    u = User(username=username, email=app.email, first_name=first[:150], last_name=last.strip()[:150],
             email_verified=True, email_verified_at=timezone.now(), **fields)
    u.set_password(temp_password())     # replaced through the set-password link
    u.save()
    return u


def award_individual(app):
    """Returns (user, created)."""
    u = find_account(app)
    created = u is None
    if created:
        u = _new_account(app, app.email, role=Role.STUDENT, is_trial_account=True, institution=app.institution, occupation=app.occupation)
    u.subscribed_until = _award_end(u.subscribed_until)
    u.save(update_fields=['subscribed_until'])
    app.user, app.awarded_until = u, u.subscribed_until
    return u, created


def _new_college_code(name):
    base = slugify(name)[:14].strip('-') or 'college'
    code, n = base, 1
    while College.objects.filter(code=code).exists() or User.objects.filter(username=f'{code}-admin').exists():
        n += 1
        code = f'{base}-{n}'
    return code


def award_college(app, college=None):
    """Returns (college, new College Admin or None). A college with no end date keeps it."""
    admin = None
    if college is None:
        college = College.objects.create(name=app.institution, code=_new_college_code(app.institution), contact_email=app.email,
                                         subscription_until=_award_end(None))
        admin = _new_account(app, make_username(college, 'admin'), role=Role.COLLEGE_ADMIN, college=college)
    elif not (college.subscription_active and college.subscription_until is None):
        lapsed = not college.subscription_active
        college.subscription_until = _award_end(None if lapsed else college.subscription_until)
        college.subscription_active = True
        college.save(update_fields=['subscription_until', 'subscription_active'])
    app.awarded_college, app.awarded_until = college, college.subscription_until
    return college, admin


def erase_personal_data(user):
    """Called when an account is anonymised. Runs before the e-mail address is erased."""
    apps = FreeYearApplication.objects.filter(user=user)
    if user.email:
        apps = apps | FreeYearApplication.objects.filter(email__iexact=user.email)
    apps.filter(status=FreeYearApplication.PENDING).update(status=FreeYearApplication.REJECTED, review_note='The applicant deleted their account.')
    apps.update(name='Deleted user', email='', phone='', message='', user=None, institution='')
