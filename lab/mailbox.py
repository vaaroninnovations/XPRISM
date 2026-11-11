"""The super admins' mailbox.

Outgoing mail is written on the site (address, subject, text) and sent in the XPRISM e-mail template, with a
Reply-To that brings answers back here. Incoming mail is read from an ordinary mail account over IMAP: on the
"Check for new mail" button, when the inbox is opened (at most every few minutes), and by the fetch_mail command.

Received mail is untrusted. Only its text is kept and shown, never its HTML, and attachments are listed by name
and size but not stored.
"""
import email
import hashlib
import html
import imaplib
import logging
import re
import threading
from email import policy
from email.utils import getaddresses, make_msgid, parseaddr, parsedate_to_datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import connections, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from .emails import LOGO_CID, _message
from .models import MailMessage

log = logging.getLogger(__name__)
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
MAX_BODY = 200_000
MAX_RECIPIENTS = 20


def can_send():
    """Until SMTP is configured, mail only goes to the server's console: it must not be recorded as sent to real people."""
    return settings.DEBUG or 'console' not in settings.EMAIL_BACKEND


def can_receive():
    return bool(settings.IMAP_HOST and settings.IMAP_USER)


def address():
    """Where replies should come back to: MAILBOX_ADDRESS, else the IMAP account, else the address mail is sent from.
    Only a real e-mail address counts. A sending service's login name (Resend's is just "resend") is not one, and a
    mail server refuses a message whose Reply-To is not an address."""
    for candidate in (settings.MAILBOX_ADDRESS, settings.IMAP_USER, parseaddr(settings.DEFAULT_FROM_EMAIL)[1]):
        candidate = (candidate or '').strip()
        try:
            validate_email(candidate)
        except ValidationError:
            continue
        return candidate
    return ''


def sent_today():
    return MailMessage.objects.filter(direction=MailMessage.OUT, created_at__gte=timezone.now() - timezone.timedelta(hours=24)).count()


# ---------------------------------------------------------------- the template
def template_context(subject, body, greeting='', signoff=''):
    return {'subject': subject, 'body': body, 'greeting': greeting.strip(), 'signoff': signoff.strip() or f'The {settings.SITE_NAME} team',
            'company': settings.SITE_INSTITUTION, 'reply_to': address()}


def preview_html(subject, body, greeting='', signoff='', logo_url=''):
    """The message as its recipient will see it, with the logo loaded from the site instead of from the e-mail."""
    ctx = {'name': '', 'site_name': settings.SITE_NAME, 'site_full_name': settings.SITE_FULL_NAME, 'support_email': settings.LEGAL['contact_email'],
           'logo_cid': LOGO_CID, **template_context(subject, body, greeting, signoff)}
    return render_to_string('emails/mailbox_message.html', ctx).replace(f'cid:{LOGO_CID}', logo_url)


# ---------------------------------------------------------------- sending
def compose(to, subject, body, user, greeting='', signoff='', parent=None):
    """Save an outgoing message and send it once the transaction commits. Returns the MailMessage."""
    host = (address().split('@')[-1] or 'localhost').strip()
    m = MailMessage.objects.create(
        direction=MailMessage.OUT, status=MailMessage.QUEUED, message_id=make_msgid(domain=host), in_reply_to=parent.message_id if parent else '',
        parent=parent, root=(parent.root or parent) if parent else None, from_name=settings.SITE_NAME, from_email=address(), to=', '.join(to),
        subject=subject[:255], body=body, greeting=greeting.strip()[:120], signoff=signoff.strip()[:120], is_read=True, sent_by=user, date=timezone.now())

    def deliver():
        try:
            msg = _message(to, '', m.subject, 'mailbox_message', template_context(m.subject, m.body, m.greeting, m.signoff))
            if address():
                msg.reply_to = [address()]
            msg.extra_headers['Message-ID'] = m.message_id
            if m.in_reply_to:
                msg.extra_headers['In-Reply-To'] = m.in_reply_to
                msg.extra_headers['References'] = m.in_reply_to
            msg.send(fail_silently=False)
        except Exception as e:  # recorded on the message, where the super admin can see it and send again
            log.exception('Could not send mailbox message %s', m.pk)
            MailMessage.objects.filter(pk=m.pk).update(status=MailMessage.FAILED, error=str(e)[:500])
        else:
            MailMessage.objects.filter(pk=m.pk).update(status=MailMessage.SENT, error='', date=timezone.now())

    def in_thread():
        try:
            deliver()
        finally:
            connections.close_all()

    transaction.on_commit(lambda: threading.Thread(target=in_thread, daemon=True).start() if getattr(settings, 'EMAIL_ASYNC', False) else deliver())
    return m


# ---------------------------------------------------------------- receiving
def _text_of(msg):
    """The readable text of a message: its plain part, or its HTML with the markup removed."""
    try:
        part = msg.get_body(preferencelist=('plain', 'html'))
        if part is None:
            return ''
        content = part.get_content()
        if not isinstance(content, str):
            content = content.decode('utf-8', 'replace')
        if part.get_content_type() == 'text/html':
            content = re.sub(r'(?is)<(script|style|head).*?</\1>', ' ', content)
            content = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>|</li>', '\n', content)
            content = html.unescape(strip_tags(content))
        content = re.sub(r'[ \t\xa0]+\n', '\n', content.replace('\r\n', '\n').replace('\r', '\n'))
        return re.sub(r'\n{3,}', '\n\n', content).strip()[:MAX_BODY]
    except Exception:  # a malformed message must not stop the rest of the inbox arriving
        log.exception('Could not read the body of a received message')
        return '(This message could not be read.)'


def _attachments_of(msg):
    out = []
    try:
        for part in msg.iter_attachments():
            data = part.get_payload(decode=True) or b''
            out.append({'name': (part.get_filename() or 'attachment')[:120], 'size': len(data)})
    except Exception:
        log.exception('Could not list the attachments of a received message')
    return out[:30]


def store(raw):
    """Keep one received message. Returns the MailMessage, or None if it is already here."""
    msg = email.message_from_bytes(raw, policy=policy.default)
    mid = (str(msg.get('Message-ID') or '').strip() or f'<{hashlib.sha1(raw).hexdigest()}@no-message-id>')[:255]
    if MailMessage.objects.filter(message_id=mid).exists():
        return None
    name, addr = parseaddr(str(msg.get('From') or ''))
    to = ', '.join(a for _, a in getaddresses([str(v) for v in msg.get_all('To', [])]) if a)
    try:
        date = parsedate_to_datetime(str(msg.get('Date')))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        date = min(date, timezone.now())
    except (TypeError, ValueError):
        date = timezone.now()
    irt = str(msg.get('In-Reply-To') or '').strip()[:255]
    parent = MailMessage.objects.filter(message_id=irt).first() if irt else None
    return MailMessage.objects.create(
        direction=MailMessage.IN, status=MailMessage.RECEIVED, message_id=mid, in_reply_to=irt, parent=parent, root=(parent.root or parent) if parent else None,
        from_name=name[:120], from_email=addr[:254].lower(), to=to[:2000], subject=(str(msg.get('Subject') or '').strip() or '(no subject)')[:255],
        body=_text_of(msg), attachments=_attachments_of(msg), date=date)


def fetch(limit=200):
    """Bring in mail that has arrived since the last check. Returns (number of new messages, error text or '')."""
    if not can_receive():
        return 0, 'Receiving is not set up: add IMAP_HOST, IMAP_USER and IMAP_PASSWORD to .env.'
    latest = MailMessage.objects.filter(direction=MailMessage.IN).order_by('-date').values_list('date', flat=True).first()
    since = (latest - timezone.timedelta(days=2)) if latest else timezone.now() - timezone.timedelta(days=settings.MAILBOX_FETCH_DAYS)
    box, new = None, 0
    try:
        cls = imaplib.IMAP4_SSL if settings.IMAP_USE_SSL else imaplib.IMAP4
        box = cls(settings.IMAP_HOST, settings.IMAP_PORT, timeout=settings.IMAP_TIMEOUT)
        box.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        box.select(settings.IMAP_FOLDER, readonly=True)             # read-only: nothing is marked as seen or removed on the mail server
        typ, data = box.uid('search', None, 'SINCE', f'{since.day:02d}-{MONTHS[since.month - 1]}-{since.year}')
        if typ != 'OK':
            return 0, 'The mail server did not return the inbox.'
        for uid in (data[0] or b'').split()[-limit:]:
            typ, parts = box.uid('fetch', uid, '(BODY.PEEK[])')
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple) and len(p) > 1), None)
            if typ == 'OK' and raw and store(raw):
                new += 1
    except Exception as e:  # wrong password, server down, time-out: say so on the page, keep what is already here
        log.exception('Could not fetch mail')
        return new, f'Could not reach the mail server: {str(e)[:200]}'
    finally:
        if box is not None:
            try:
                box.logout()
            except Exception:
                pass
    return new, ''


def erase_for(address_):
    """Remove the mail to and from an address whose owner asked for their data to be deleted."""
    if address_:
        MailMessage.objects.filter(from_email__iexact=address_).delete()
        MailMessage.objects.filter(direction=MailMessage.OUT, to__iexact=address_).delete()
