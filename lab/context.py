import json

from django.conf import settings
from django.utils.safestring import mark_safe

from .models import ContactRequest, DataRequest, FreeYearApplication, Role

# the pages search engines may list and analytics may measure; everything else is private to its user
PUBLIC_PAGES = ('/', '/modules/', '/documentation/', '/about/', '/contact/', '/ethics/', '/privacy/', '/terms/', '/conditions/')


def _seo(request):
    base, path = settings.SITE_URL.rstrip('/'), request.path
    public = path in PUBLIC_PAGES and not settings.SEO['noindex']
    out = {**settings.SEO, 'canonical': base + path, 'robots': 'index, follow' if public else 'noindex, nofollow',
           'image': settings.SEO['image'] or f"{base}{settings.STATIC_URL.rstrip('/')}/img/modules/hero-rota-rod.jpg"}
    if path == '/':
        data = {'@context': 'https://schema.org', '@type': 'EducationalOrganization', 'name': settings.SITE_NAME, 'alternateName': settings.SITE_FULL_NAME,
                'url': base + '/', 'logo': f"{base}{settings.STATIC_URL.rstrip('/')}/img/icon-512.png", 'description': settings.SEO['description'], 'parentOrganization': {'@type': 'Organization', 'name': settings.LEGAL['org_name']}}
        out['jsonld'] = mark_safe(json.dumps(data).replace('<', '\\u003c'))
    return out


def _analytics(request):
    """IDs for the consent-gated loader. Only anonymous visitors on public pages: never students' work, sign-in tokens or staff pages."""
    ids = {'ga': settings.GOOGLE_ANALYTICS_ID, 'gtm': settings.GOOGLE_TAG_MANAGER_ID}
    return ids if any(ids.values()) and not request.user.is_authenticated and request.path in PUBLIC_PAGES else None


def site(request):
    u = request.user
    college = getattr(u, 'college', None) if u.is_authenticated else None
    nav = []
    if u.is_authenticated:
        r = u.role
        if r == Role.STUDENT:
            nav = [('My assignments', '/student/'), ('Practice lab', '/modules/')] if (u.has_full_access or not u.is_trial_account) else [('Lab (free trial)', '/modules/'), ('Subscribe', '/subscribe/')]
        if r in (Role.FACULTY, Role.LAB_ASSISTANT):
            nav = [('Dashboard', '/faculty/'), ('Batches', '/faculty/batches/'), ('Experiments', '/modules/')]
        if r == Role.COLLEGE_ADMIN:
            nav = [('College', '/college/'), ('Staff', '/college/users/'), ('Batches', '/faculty/batches/'), ('Experiments', '/college/experiments/'), ('Requests', '/college/requests/'), ('Audit log', '/college/audit/')]
        if u.is_platform_admin:
            nav = [('Platform', '/platform/'), ('Contact', '/platform/contact/'), ('Free month', '/platform/free-year/'), ('Colleges', '/platform/colleges/'), ('Trial users', '/platform/trials/'), ('Catalogue', '/platform/experiments/'), ('Batches', '/faculty/batches/'), ('Requests', '/college/requests/'), ('Audit log', '/college/audit/'), ('Django admin', '/admin/')]
    open_requests = 0
    if u.is_authenticated and (u.is_platform_admin or u.role == Role.COLLEGE_ADMIN):
        qs = DataRequest.objects.filter(status=DataRequest.OPEN)
        open_requests = (qs if u.is_platform_admin else qs.filter(college=u.college)).count()
    pending_free_year = u.is_authenticated and u.is_platform_admin and FreeYearApplication.objects.filter(status=FreeYearApplication.PENDING).count()
    # the free-year offer: for visitors and free-trial users, never on top of the sign-in steps
    show_free_year = not request.path.startswith(('/accounts/', '/consent/'))
    if show_free_year and u.is_authenticated:
        show_free_year = (not u.has_full_access and not u.is_shared_demo and not u.must_change_password
                          and u.consent_version == settings.POLICY_VERSION and u.ethics_version == settings.ETHICS_VERSION
                          and not u.free_year_applications.exclude(status=FreeYearApplication.REJECTED).exists())
    return {
        'PENDING_FREE_YEAR': pending_free_year, 'SHOW_FREE_YEAR': show_free_year,
        'PENDING_CONTACT': u.is_authenticated and u.is_platform_admin and ContactRequest.objects.filter(status=ContactRequest.NEW).count(),
        'SEO': _seo(request), 'ANALYTICS': _analytics(request), 'ANALYTICS_CONFIGURED': bool(settings.GOOGLE_ANALYTICS_ID or settings.GOOGLE_TAG_MANAGER_ID),
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
                         and not request.path.startswith(('/documentation/', '/ethics/', '/about/','/privacy/', '/terms/', '/conditions/', '/consent/', '/accounts/'))),
        'NEEDS_EMAIL_VERIFY': bool(u.is_authenticated and u.email and not u.email_verified and not u.is_platform_admin),
        'ETHICS_VERSION': settings.ETHICS_VERSION, 'TRIAL_HOURS': settings.TRIAL_VISIT_MAX_HOURS,
    }
