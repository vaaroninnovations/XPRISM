from django.conf import settings

from .models import DataRequest, Role


def site(request):
    u = request.user
    college = getattr(u, 'college', None) if u.is_authenticated else None
    nav = []
    if u.is_authenticated:
        r = u.role
        if r == Role.STUDENT:
            nav = [('My assignments', '/student/'), ('Practice lab', '/')] if (u.has_full_access or not u.is_trial_account) else [('Lab (free trial)', '/'), ('Subscribe', '/subscribe/')]
        if r in (Role.FACULTY, Role.LAB_ASSISTANT):
            nav = [('Dashboard', '/faculty/'), ('Batches', '/faculty/batches/'), ('Experiments', '/')]
        if r == Role.COLLEGE_ADMIN:
            nav = [('College', '/college/'), ('Staff', '/college/users/'), ('Batches', '/faculty/batches/'), ('Experiments', '/college/experiments/'), ('Requests', '/college/requests/'), ('Audit log', '/college/audit/')]
        if u.is_platform_admin:
            nav = [('Platform', '/platform/'), ('Colleges', '/platform/colleges/'), ('Trial users', '/platform/trials/'), ('Catalogue', '/platform/experiments/'), ('Batches', '/faculty/batches/'), ('Requests', '/college/requests/'), ('Audit log', '/college/audit/'), ('Django admin', '/admin/')]
    open_requests = 0
    if u.is_authenticated and (u.is_platform_admin or u.role == Role.COLLEGE_ADMIN):
        qs = DataRequest.objects.filter(status=DataRequest.OPEN)
        open_requests = (qs if u.is_platform_admin else qs.filter(college=u.college)).count()
    return {
        'SITE_NAME': settings.SITE_NAME, 'SITE_TAGLINE': settings.SITE_TAGLINE,
        'SITE_FULL_NAME': settings.SITE_FULL_NAME, 'SITE_CREATOR': settings.SITE_CREATOR,
        'SITE_CREATOR_EMAIL': settings.SITE_CREATOR_EMAIL, 'SITE_INSTITUTION': settings.SITE_INSTITUTION,
        'SITE_AIM': settings.SITE_AIM, 'SITE_AIM_SHORT': settings.SITE_AIM_SHORT,
        'SITE_LOCATION': (college.location_text if college and college.location_text else settings.SITE_DEFAULT_LOCATION),
        'COLLEGE': college, 'NAV': nav, 'LEGAL': settings.LEGAL, 'POLICY_VERSION': settings.POLICY_VERSION,
        'POLICY_EFFECTIVE': settings.POLICY_EFFECTIVE, 'OPEN_REQUESTS': open_requests, 'Role': Role,
        'DATA_RETENTION_YEARS': settings.DATA_RETENTION_YEARS,
        'IS_TRIAL': u.is_authenticated and not u.has_full_access,
        # shown after the temporary-password and policy-consent steps, never on top of them
        'NEEDS_ETHICS': (u.is_authenticated and u.ethics_version != settings.ETHICS_VERSION and not u.must_change_password
                         and u.consent_version == settings.POLICY_VERSION
                         and not request.path.startswith(('/ethics/', '/about/', '/privacy/', '/terms/', '/conditions/', '/consent/', '/accounts/'))),
        'ETHICS_VERSION': settings.ETHICS_VERSION, 'TRIAL_HOURS': settings.TRIAL_VISIT_MAX_HOURS,
    }
