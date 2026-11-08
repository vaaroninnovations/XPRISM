from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme

OPEN_PREFIXES = ('/assets/', '/contact', '/robots.txt', '/sitemap.xml', '/accounts/logout', '/privacy', '/terms', '/conditions', '/ethics', '/about', '/documentation', '/consent', '/accounts/password/force', '/accounts/verify', '/invitation/opt-out', '/favicon')
# what a public demo login may change: enough to try assigning, grading and submitting. Everything else (people, passwords, settings, batches, data requests) is refused.
SHARED_DEMO_ALLOWED = {'contact', 'logout', 'consent', 'ethics_agreement', 'api_submit', 'assignment_new', 'assignment_edit', 'attempt_detail', 'invitation_opt_out'}


def _shared_demo_refusal(request):
    try:
        if resolve(request.path_info).url_name in SHARED_DEMO_ALLOWED:
            return None
    except Resolver404:
        return None
    text = 'This is a shared demo, so that action is switched off. Write to us for your own college account.'
    if request.path.startswith('/api/'):
        return JsonResponse({'error': text}, status=403)
    messages.info(request, text)
    back = request.META.get('HTTP_REFERER', '')
    return redirect(back if url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}) else 'home')


class AccountGateMiddleware:
    """Logged-in users must (1) replace a temporary password and (2) accept the current policies. Public demo logins cannot change most things."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, 'user', None)
        if u is not None and u.is_authenticated and u.is_shared_demo and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            refusal = _shared_demo_refusal(request)
            if refusal is not None:
                return refusal
        if u is not None and u.is_authenticated and not request.path.startswith(OPEN_PREFIXES):
            if u.must_change_password:
                return redirect(reverse('force_password') + f'?next={request.get_full_path()}')
            if u.consent_version != settings.POLICY_VERSION:
                if request.path.startswith('/api/'):
                    return JsonResponse({'error': 'Please accept the updated terms first.'}, status=403)
                return redirect(reverse('consent') + f'?next={request.get_full_path()}')
        return self.get_response(request)
