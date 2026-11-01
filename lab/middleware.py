from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

OPEN_PREFIXES = ('/assets/', '/accounts/logout', '/privacy', '/terms', '/conditions', '/ethics', '/about', '/documentation', '/consent', '/accounts/password/force', '/accounts/verify', '/favicon')


class AccountGateMiddleware:
    """Logged-in users must (1) replace a temporary password and (2) accept the current policies."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, 'user', None)
        if u is not None and u.is_authenticated and not request.path.startswith(OPEN_PREFIXES):
            if u.must_change_password:
                return redirect(reverse('force_password') + f'?next={request.get_full_path()}')
            if u.consent_version != settings.POLICY_VERSION:
                if request.path.startswith('/api/'):
                    from django.http import JsonResponse
                    return JsonResponse({'error': 'Please accept the updated terms first.'}, status=403)
                return redirect(reverse('consent') + f'?next={request.get_full_path()}')
        return self.get_response(request)
