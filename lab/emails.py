"""Transactional e-mails sent automatically after sign-up: address verification and welcome.

Mails are sent after the database transaction commits (so a rolled-back sign-up never sends
anything) and, outside tests, on a background thread so a slow SMTP server never delays the
sign-up page. A failure to send is logged and never breaks the sign-up itself.
"""
import logging
import threading
from email.mime.image import MIMEImage

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.db import connections, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import CATEGORIES, Experiment, FreeYearInvitation, Role

log = logging.getLogger(__name__)
LOGO_CID = 'xprism-logo'


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Signed, expiring token (PASSWORD_RESET_TIMEOUT, default 3 days). It stops working once the
    address is verified or the e-mail address on the account changes."""
    key_salt = 'lab.emails.EmailVerificationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.email}{user.email_verified}{timestamp}'


verification_token = EmailVerificationTokenGenerator()


def _base_url(request=None):
    if request is not None:
        return request.build_absolute_uri('/').rstrip('/')
    return settings.SITE_URL.rstrip('/')


def verification_url(user, request=None):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return _base_url(request) + reverse('verify_email', args=[uid, verification_token.make_token(user)])


def set_password_url(user, request=None):
    """One-time link for an account the applicant did not choose a password for."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return _base_url(request) + reverse('password_reset_confirm', args=[uid, default_token_generator.make_token(user)])


def _deliver(msg):
    try:
        msg.send(fail_silently=False)
    except Exception:  # never let e-mail problems break the request
        log.exception('Could not send e-mail "%s" to %s', msg.subject, msg.to)


def _attach_logo(msg):
    """Embed the logo in the message, so it shows without loading anything from the site."""
    try:
        logo = MIMEImage((settings.BASE_DIR / 'static' / 'assets' / 'img' / 'xprism-lockup.png').read_bytes())
    except OSError:
        log.exception('Could not read the logo for e-mails')
        return
    logo.add_header('Content-ID', f'<{LOGO_CID}>')
    logo.add_header('Content-Disposition', 'inline', filename='xprism-logo.png')
    msg.mixed_subtype = 'related'
    msg.attach(logo)


def _message(to, name, subject, template, ctx):
    ctx = {'name': name, 'site_name': settings.SITE_NAME, 'site_full_name': settings.SITE_FULL_NAME,
           'support_email': settings.LEGAL['contact_email'], 'logo_cid': LOGO_CID, **ctx}
    msg = EmailMultiAlternatives(subject, render_to_string(f'emails/{template}.txt', ctx), settings.DEFAULT_FROM_EMAIL, to)
    msg.attach_alternative(render_to_string(f'emails/{template}.html', ctx), 'text/html')
    _attach_logo(msg)
    return msg


def _send_to(to, name, subject, template, ctx):
    msg = _message(to, name, subject, template, ctx)
    if getattr(settings, 'EMAIL_ASYNC', False):
        threading.Thread(target=_deliver, args=(msg,), daemon=True).start()
    else:
        _deliver(msg)


def _send(user, subject, template, ctx):
    _send_to([user.email], user.first_name or user.username, subject, template, {'user': user, **ctx})


def _super_admin_addresses():
    admins = get_user_model().objects.filter(Q(role=Role.SUPERADMIN) | Q(is_superuser=True), is_active=True).exclude(email='')
    return sorted({a.email.lower() for a in admins} | ({settings.SUBSCRIPTION_CONTACT.lower()} if settings.SUBSCRIPTION_CONTACT else set()))


def send_free_year_received(app, request=None):
    """Tell the super admins there is an application to review, and the applicant that it arrived."""
    review_url = _base_url(request) + reverse('free_year_applications')

    def go():
        to = _super_admin_addresses()
        if to:
            _send_to(to, 'Super admin', f'New free-year application #{app.pk}', 'free_year_review', {'app': app, 'review_url': review_url})
        _send_to([app.email], app.name, f'We received your {settings.SITE_NAME} application', 'free_year_received', {'app': app})
    transaction.on_commit(go)


def send_free_year_approved(app, username=None, college=None, set_password_url=None, request=None):
    login_url = _base_url(request) + reverse('login')
    transaction.on_commit(lambda: _send_to([app.email], app.name, f'Your free year of {settings.SITE_NAME} is ready', 'free_year_approved', {
        'app': app, 'username': username, 'college': college, 'set_password_url': set_password_url, 'login_url': login_url,
        'valid_days': max(1, settings.PASSWORD_RESET_TIMEOUT // 86400)}))


def send_free_year_declined(app):
    transaction.on_commit(lambda: _send_to([app.email], app.name, f'Your {settings.SITE_NAME} application', 'free_year_declined', {'app': app}))


def send_free_year_invitations(invitations, note='', request=None):
    """Send one at a time on a single background thread, recording how each went, so a long list never delays the page or floods the mail server."""
    base = _base_url(request)
    subject = f'Invitation to your institution: {settings.SITE_NAME} virtual pharmacology lab, free of cost for 1 year'
    experiments = list(Experiment.objects.filter(is_active=True))
    content = {'note': note, 'apply_url': f'{base}/?apply=1', 'company': settings.SITE_INSTITUTION, 'company_location': settings.SITE_COMPANY_LOCATION,
               'creator': settings.SITE_CREATOR, 'n_modules': len(experiments),
               'modules': [{'name': name, 'items': [e for e in experiments if e.category == category]} for category, name, _ in CATEGORIES]}

    def deliver():
        for inv in invitations:
            opt_out_url = base + reverse('invitation_opt_out', args=[inv.token])
            try:
                msg = _message([inv.email], '', subject, 'free_year_invitation', {**content, 'opt_out_url': opt_out_url})
                msg.extra_headers['List-Unsubscribe'] = f'<{opt_out_url}>'
                msg.send(fail_silently=False)
            except Exception:
                log.exception('Could not send the invitation to %s', inv.email)
                FreeYearInvitation.objects.filter(pk=inv.pk).update(status=FreeYearInvitation.FAILED)
            else:
                FreeYearInvitation.objects.filter(pk=inv.pk).update(status=FreeYearInvitation.SENT, sent_at=timezone.now())

    def deliver_in_thread():
        try:
            deliver()
        finally:
            connections.close_all()

    def go():
        if getattr(settings, 'EMAIL_ASYNC', False):
            threading.Thread(target=deliver_in_thread, daemon=True).start()
        else:
            deliver()
    transaction.on_commit(go)


def send_verification_email(user, request=None):
    if not user.email or user.email_verified:
        return False
    url = verification_url(user, request)
    days = max(1, settings.PASSWORD_RESET_TIMEOUT // 86400)
    _send(user, f'Verify your e-mail address for {settings.SITE_NAME}', 'verify_email', {'verify_url': url, 'valid_days': days})
    return True


def send_welcome_email(user, request=None, batch=None):
    if not user.email:
        return False
    _send(user, f'Welcome to {settings.SITE_NAME}', 'welcome', {
        'batch': batch, 'is_trial': user.is_trial_account, 'login_url': _base_url(request) + reverse('login'),
        'lab_url': _base_url(request) + reverse('modules'), 'subscribe_url': _base_url(request) + reverse('subscribe'),
        'subscription_contact': settings.SUBSCRIPTION_CONTACT,
    })
    return True


def send_signup_emails(user, request=None, batch=None):
    """Called by every self sign-up path: verification first, then welcome, once the account is saved."""
    if not user.email:
        return

    def go():
        send_verification_email(user, request)
        send_welcome_email(user, request, batch)
    transaction.on_commit(go)
