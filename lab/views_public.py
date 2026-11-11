import html
import json
import re

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.cache import cache
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import access
from .contact import TOPICS
from .context import PUBLIC_PAGES
from . import free_year
from .emails import send_contact_received, send_free_year_received
from .forms import ContactForm, FreeYearApplicationForm
from .models import CATEGORIES, LEVELS, Assignment, Attempt, Experiment, FreeYearApplication, FreeYearInvitation, Role
from .permissions import audit, client_ip


FEATURED = (4, 11, 12, 14, 18, 21)      # the experiments previewed on the home page


def _catalogue(request):
    """The experiments this visitor can see, each marked with how they may open it."""
    u = request.user
    exps = list(Experiment.objects.filter(is_active=True))
    assigned, trial = {}, None
    if u.is_authenticated:
        if u.college_id:
            disabled = set(u.college.disabled_experiments.values_list('pk', flat=True))
            exps = [e for e in exps if e.pk not in disabled]
        if not u.has_full_access:
            access.consume_open(u, 'index')            # returning to the index ends any open trial visit
            trial = access.states(u)
        elif u.role == Role.STUDENT:
            for a in Assignment.objects.filter(batch__enrollments__student=u, batch__archived=False).select_related('experiment'):
                assigned.setdefault(a.experiment_id, a)
    for e in exps:
        e.locked = not u.is_authenticated
        e.assignment = assigned.get(e.pk)
        e.trial_state = (trial.get(e.pk, access.AVAILABLE) if trial is not None else None)
        e.used = e.trial_state == access.USED
    return exps, trial is not None


def _sections(exps):
    return [dict(cat=c, name=n, sub=sub, items=[e for e in exps if e.category == c]) for c, n, sub in CATEGORIES]


def _levels(exps):
    out = []
    for level, sub in LEVELS:
        items = [e for e in exps if e.level == level]
        if items:
            out.append(dict(level=level, sub=sub, n=len(items), groups=[s for s in _sections(items) if s['items']]))
    return out


def landing(request):
    exps, trial = _catalogue(request)
    return render(request, 'lab/landing.html', {'featured': [e for e in exps if e.no in FEATURED], 'sections': _sections(exps), 'n_total': len(exps), 'trial': trial})


def modules(request):
    exps, trial = _catalogue(request)
    left = sum(1 for e in exps if e.trial_state == access.AVAILABLE) if trial else None
    return render(request, 'lab/modules.html', {'levels': _levels(exps), 'sections': _sections(exps), 'n_total': len(exps), 'trial': trial, 'trial_left': left})


def documentation(request):
    return render(request, 'legal/documentation.html', {'sections': _sections(list(Experiment.objects.filter(is_active=True))), 'page': 'documentation'})


def subscribe(request):
    """'Subscription only' page: shown when a free-trial visit has been used."""
    u = request.user
    exp = None
    slug = request.GET.get('exp')
    if slug:
        exp = Experiment.objects.filter(slug=slug).first()
    left = []
    if u.is_authenticated and not u.has_full_access:
        access.consume_open(u, 'index')
        st = access.states(u)
        qs = Experiment.objects.filter(is_active=True)
        if u.college_id:
            qs = qs.exclude(pk__in=u.college.disabled_experiments.values('pk'))
        left = [e for e in qs if st.get(e.pk, access.AVAILABLE) == access.AVAILABLE]
    expired_college = u.is_authenticated and u.college and not u.college.is_subscribed
    return render(request, 'lab/subscribe.html', {'exp': exp, 'left': left, 'expired_college': expired_college,
                                                  'contact': settings.SUBSCRIPTION_CONTACT or settings.LEGAL['contact_email']}, status=402 if exp else 200)


@require_POST
def free_year_apply(request):
    """Receives the free-year pop-up. Says the same thing whether or not the e-mail is already known, so it cannot be used to discover who has applied."""
    u = request.user
    if u.is_authenticated and u.has_full_access:
        return JsonResponse({'error': 'Your account already has full access.'}, status=400)
    form = FreeYearApplicationForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)
    if form.cleaned_data['website']:
        return JsonResponse({'ok': True})
    # X-Real-IP is set by nginx, so unlike X-Forwarded-For a visitor cannot choose it
    key = f"free-year-ip:{request.META.get('HTTP_X_REAL_IP') or client_ip(request)}"
    cache.add(key, 0, 3600)
    if cache.incr(key) > settings.FREE_MONTH_MAX_PER_HOUR:
        return JsonResponse({'error': 'Too many applications from this network. Please try again in an hour.'}, status=429)
    app = form.save(commit=False)
    if u.is_authenticated:
        app.user = u
        app.email = u.email or app.email
    with transaction.atomic():
        earlier = FreeYearApplication.objects.select_for_update().filter(email__iexact=app.email).exclude(status=FreeYearApplication.REJECTED).first()
        if earlier is None:
            app.save()
            audit(request, 'free_year_applied', f'#{app.pk}', kind=app.kind)
            if not (settings.FREE_MONTH_AUTO_APPROVE and free_year.auto_approve(request, app)):
                send_free_year_received(app, request)
        elif earlier.status == FreeYearApplication.PENDING and settings.FREE_MONTH_AUTO_APPROVE:
            free_year.auto_approve(request, earlier)        # they applied before and are still waiting: do not leave them there
    # the same answer for every application, so it never shows whether an address was already known or approved
    return JsonResponse({'ok': True, 'email': app.email, 'auto': settings.FREE_MONTH_AUTO_APPROVE})


def invitation_opt_out(request, token):
    """Link in every invitation. Changes nothing on GET, because mail scanners open links by themselves."""
    inv = get_object_or_404(FreeYearInvitation, token=token)
    if request.method == 'POST' and not inv.opted_out_at:
        inv.opted_out_at = timezone.now()
        inv.save(update_fields=['opted_out_at'])
        audit(request, 'free_year_invitation_opt_out', f'#{inv.pk}')
    return render(request, 'lab/invitation_opt_out.html', {'inv': inv})


CONTACT_MAX_PER_HOUR = 10


def contact(request):
    u = request.user
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if request.POST.get('website'):         # a hidden field only bots fill in: looks like success, stores nothing
            return redirect(f"{reverse('contact')}?sent=XP-000000")
        key = f"contact-ip:{request.META.get('HTTP_X_REAL_IP') or client_ip(request)}"
        cache.add(key, 0, 3600)
        if cache.incr(key) > CONTACT_MAX_PER_HOUR:
            form.add_error(None, 'Too many requests from this network. Please try again in an hour.')
        elif form.is_valid():
            with transaction.atomic():
                item = form.save(commit=False)
                item.subtopic = form.cleaned_data['subtopic']
                if u.is_authenticated:
                    item.user = u
                item.save()
                audit(request, 'contact_received', item.reference, topic=item.topic)
                send_contact_received(item, request)
            return redirect(f"{reverse('contact')}?sent={item.reference}")
    else:
        topic = request.GET.get('topic', '')
        initial = {'topic': topic} if topic in {k for k, _, _ in TOPICS} else {}
        if u.is_authenticated:
            initial.update(name=u.get_full_name(), email=u.email, institution=(u.college.name if u.college else u.institution))
        form = ContactForm(initial=initial)
    sent = request.GET.get('sent', '') if request.method == 'GET' else ''
    return render(request, 'lab/contact.html', {'form': form, 'topics': {k: subs for k, _, subs in TOPICS}, 'sent': sent if re.fullmatch(r'XP-\d{6}', sent) else ''})


@require_GET
def robots_txt(request):
    base = settings.SITE_URL.rstrip('/')
    if settings.SEO['noindex']:
        lines = ['User-agent: *', 'Disallow: /']
    else:
        private = ['/admin/', '/accounts/', '/api/', '/platform/', '/college/', '/faculty/', '/student/', '/me/', '/home/', '/consent/', '/agreement/', '/subscribe/', '/invitation/', '/experiments/']
        lines = ['User-agent: *', 'Allow: /'] + [f'Disallow: {p}' for p in private] + ['', f'Sitemap: {base}/sitemap.xml']
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')


@require_GET
def sitemap_xml(request):
    """The public pages only. Module pages need an account, so they are described on /modules/ instead of being listed here."""
    base = settings.SITE_URL.rstrip('/')
    urls = '' if settings.SEO['noindex'] else ''.join(f'<url><loc>{html.escape(base + p)}</loc></url>' for p in PUBLIC_PAGES)
    body = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
    return HttpResponse(body, content_type='application/xml; charset=utf-8')


def legal(request, page):
    tpl = {'privacy': 'legal/privacy.html', 'terms': 'legal/terms.html', 'conditions': 'legal/conditions.html', 'ethics': 'legal/ethics.html', 'about': 'legal/about.html'}[page]
    return render(request, tpl, {'page': page})


@require_GET
def healthz(request):
    return HttpResponse('ok', content_type='text/plain')


# ------------------------------------------------------------------ experiment pages
# How to read each module's own answer for auto-scoring: (selector of the student's answer, JS expression of the truth, kind, tolerance %)
EXP_PROBES = {
    1: ('#routeDeduction', 'codedRoute', 'choice', 0),
    2: ('#unknownDrugDeduction', 'mysteryDrugKey', 'choice', 0),
    3: ('#unknownDeductionSelect', 'assignedMysteryDrugKey', 'choice', 0),
    4: ('#unknownDrugDeduction', 'mysteryDrugKey', 'choice', 0),
    5: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    9: ('#unknownDrugDeduction', 'mysteryDrugKey', 'choice', 0),
    10: ('#unknownDrugDeduction', 'S.mystery[S.mode]', 'choice', 0),
    11: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    13: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    14: ('#answerIn', 'TRUE_T', 'number', 10),
    15: ('#answerIn', 'TRUE_T', 'number', 10),
    16: ('#answerIn', 'TRUE_T', 'number', 10),
    17: ('#answerIn', 'TRUE_T', 'number', 10),
    18: ('#answerIn', 'TRUE_PA2', 'number', 3.5),
    19: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    20: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    21: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    26: ('#answerIn', 'trueFold()', 'number', 15),
    27: ('#answerIn', 'trueIC50()', 'number', 25),
    28: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    29: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    30: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    31: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    32: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    33: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
    34: ('#unknownDrugDeduction', 'mysteryKey', 'choice', 0),
}

FACULTY_BLOCK = re.compile(r'<div class="hidden md:block text-right">\s*<div class="text-xs font-semibold text-slate-800 flex items-center justify-end space-x-1\.5">.*?Dept\. of Pharmacology</div>\s*</div>', re.S)


def _user_block(request):
    u = request.user
    who = html.escape(u.display_name)
    if u.has_full_access:
        sub = html.escape(f'{u.get_role_display()}{" • " + u.college.name if u.college else ""}')
        dot = 'bg-emerald-500'
    else:
        sub, dot = 'Free trial • one visit per module', 'bg-amber-400'
    return (f'<div class="hidden md:block text-right"><div class="text-xs font-semibold text-slate-800 flex items-center justify-end space-x-1.5">'
            f'<span class="w-2 h-2 rounded-full {dot} animate-pulse"></span><span>{who}</span></div>'
            f'<div class="text-[11px] text-slate-500 font-mono">{sub}</div></div>')


def _closed(attempt_qs, a):
    used = attempt_qs.exclude(status=Attempt.STARTED).count()
    if timezone.now() < a.opens_at:
        return f'This assignment opens on {timezone.localtime(a.opens_at):%d %b %Y, %H:%M}.'
    if used >= a.max_attempts:
        return 'You have used all attempts for this assignment. You can still practise, but nothing will be submitted.'
    if a.is_overdue and not a.allow_late:
        return 'The due date has passed and late submissions are not accepted.'
    return None


EXP_ASSET = re.compile(r'(?<=["\'])(?:\.\.)?/assets/((?:css|js)/[\w.-]+)(?=["\'])')


def experiment_page(request, slug):
    exp = get_object_or_404(Experiment, slug=slug)
    path = settings.EXPERIMENTS_DIR / f'{slug}.html'
    if not path.exists():
        raise Http404
    u = request.user
    ctx = {'expNo': exp.no, 'title': exp.title, 'csrf': get_token(request), 'home': reverse('home') if u.is_authenticated else reverse('landing'),
           'login': reverse('login') + f'?next={request.get_full_path()}', 'feedbackUrl': reverse('api_feedback', args=[exp.slug]),
           'canRate': u.is_authenticated and u.role == Role.STUDENT and not u.is_shared_demo}
    if not u.is_authenticated:
        return redirect_to_login(request.get_full_path())
    else:
        if not u.is_platform_admin and not exp.enabled_for(u.college):
            return render(request, 'lab/message.html', {'title': 'Experiment not available', 'text': 'This experiment has been switched off for your college. Contact your college admin.'}, status=403)
        if u.ethics_version != settings.ETHICS_VERSION:
            return redirect(f'{reverse("modules")}?agree=1&next={request.get_full_path()}')
        a_id = request.GET.get('a')
        if not u.has_full_access:
            allowed, visit = access.enter(u, exp)
            if not allowed:
                return redirect(f'{reverse("subscribe")}?exp={exp.slug}')
            ctx.update(mode='trial', visitStarted=visit.started_at.isoformat(), maxHours=settings.TRIAL_VISIT_MAX_HOURS)
        elif u.role == Role.STUDENT and a_id and a_id.isdigit():
            a = get_object_or_404(Assignment.objects.select_related('batch'), pk=int(a_id), experiment=exp, batch__enrollments__student=u)
            mine = Attempt.objects.filter(assignment=a, student=u)
            att = mine.filter(status=Attempt.STARTED).first()
            if att and att.deadline and timezone.now() > att.deadline + timezone.timedelta(minutes=2):
                att.status, att.submitted_at, att.timed_out = Attempt.SUBMITTED, att.deadline, True
                att.payload = {'note': 'Time limit expired before submission.'}
                att.compute_auto_score(); att.save()
                att = None
            reason = None if att else _closed(mine, a)
            if reason:
                ctx.update(mode='closed', reason=reason, assignment=a.pk)
            else:
                if not att:
                    att = Attempt.objects.create(assignment=a, student=u)
                ctx.update(mode='assignment', attempt=att.pk, submitUrl=reverse('api_submit', args=[att.pk]),
                           examMode=a.exam_mode, deadline=att.deadline.isoformat() if att.deadline else None,
                           due=a.due_at.isoformat(), overdue=a.is_overdue, maxMarks=float(a.max_marks),
                           attemptNo=mine.exclude(status=Attempt.STARTED).count() + 1, maxAttempts=a.max_attempts,
                           backUrl=reverse('student_assignment', args=[a.pk]))
        elif u.role == Role.STUDENT:
            ctx['mode'] = 'practice'
        else:
            ctx['mode'] = 'preview'
            if request.GET.get('exam') == '1':
                ctx['examMode'] = True
    page = path.read_text(encoding='utf-8')
    page = FACULTY_BLOCK.sub(lambda m: _user_block(request), page, count=1)
    loc = (u.college.location_text if u.is_authenticated and u.college and u.college.location_text else settings.SITE_DEFAULT_LOCATION)
    page = page.replace('Aaron Innovations • Experimental Pharmacology Research &amp; Interactive Student Module', f'{html.escape(loc)} • {html.escape(settings.SITE_TAGLINE)}')
    page = page.replace('href="../index.html"', f'href="{reverse("modules")}"')
    probe = EXP_PROBES.get(exp.no)
    probe_js = ''
    if probe:
        sel, expr, kind, tol = probe
        probe_js = (f'<script>window.MCP_PROBE = function () {{ var el = document.querySelector({json.dumps(sel)}); var t = null; '
                    f'try {{ t = ({expr}); }} catch (e) {{}} return {{ given: el ? el.value : "", truth: t, kind: {json.dumps(kind)}, tol: {tol} }}; }};</script>\n')
    ctx_json = json.dumps(ctx).replace('</', '<' + chr(92) + '/')
    inject = (f'<script id="mcp-ctx" type="application/json">{ctx_json}</script>\n'
              f'{probe_js}<script src="{staticfiles_storage.url("js/rate.js")}"></script>\n'
              f'<script src="{staticfiles_storage.url("js/bridge.js")}"></script>\n</body>')
    page = page.replace('</body>', inject, 1)
    page = EXP_ASSET.sub(lambda m: staticfiles_storage.url(m[1]), page)
    resp = HttpResponse(page)
    resp['Cache-Control'] = 'no-store'
    return resp


def index_redirect(request):
    return redirect('landing', permanent=True)


def not_found(request, exception=None):
    return render(request, 'lab/message.html', {'title': 'Page not found', 'text': 'This page is not in the lab. It may have moved.', 'code': 404}, status=404)


def forbidden(request, exception=None):
    return render(request, 'lab/message.html', {'title': 'Not allowed', 'text': 'Your account does not have permission to open this page.', 'code': 403}, status=403)
