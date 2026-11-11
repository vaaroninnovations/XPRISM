"""The super admins' mailbox.

Outgoing mail is written on the site (address, subject, text) and sent in the XPRISM e-mail template, with a
Reply-To that brings answers back here. Incoming mail is read from an ordinary mail account over IMAP, or from
Resend's Receiving API: on the "Check for new mail" button, when the inbox is opened (at most every few minutes),
by the fetch_mail command, and at once when Resend calls the webhook.

Received mail is untrusted. Only its text is kept and shown, never its HTML, and attachments are listed by name
and size but not stored.
"""
import base64
import binascii
import datetime
import email
import hashlib
import hmac
import html
import imaplib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from email import policy
from email.utils import getaddresses, make_msgid, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import connections, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags, urlize

from .emails import LOGO_CID, _message
from .models import MailMessage

log = logging.getLogger(__name__)
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
MAX_BODY = 200_000
MAX_RECIPIENTS = 20
RESEND_API = 'https://api.resend.com'


def can_send():
    """Until SMTP is configured, mail only goes to the server's console: it must not be recorded as sent to real people."""
    return settings.DEBUG or 'console' not in settings.EMAIL_BACKEND


def via_imap():
    return bool(settings.IMAP_HOST and settings.IMAP_USER)


def via_resend():
    return bool(settings.RESEND_RECEIVE and settings.RESEND_API_KEY)


def can_receive():
    return via_imap() or via_resend()


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
        if '.' in candidate.rsplit('@', 1)[-1]:                 # "no-reply@localhost", the built-in default, is not somewhere a reply can go
            return candidate
    return ''


def sent_today():
    return MailMessage.objects.filter(direction=MailMessage.OUT, created_at__gte=timezone.now() - timezone.timedelta(hours=24)).count()


# ---------------------------------------------------------------- formatted text
# The compose page has a small editor: bold, italic, underline, a heading, lists and links. What it sends is rebuilt
# here from a short list of tags, each with the style the e-mail needs, and everything else is dropped. Nothing the
# browser sent reaches a recipient as it came.
RICH_STYLE = {
    'p': 'margin:0 0 14px;',
    'h2': "margin:20px 0 10px;font-family:Georgia,'Times New Roman',serif;font-size:18px;line-height:1.35;font-weight:600;color:#08193b;",
    'ul': 'margin:0 0 14px;padding-left:24px;list-style:disc;', 'ol': 'margin:0 0 14px;padding-left:24px;list-style:decimal;', 'li': 'margin:0 0 4px;',
    'blockquote': 'margin:0 0 14px;padding-left:12px;border-left:3px solid #d9d3e8;color:#475569;', 'a': 'color:#7e13b5;',
}
RICH_INLINE = {'b': 'strong', 'strong': 'strong', 'i': 'em', 'em': 'em', 'u': 'u'}
RICH_BLOCK = {'p': 'p', 'div': 'p', 'h1': 'h2', 'h2': 'h2', 'h3': 'h2', 'ul': 'ul', 'ol': 'ol', 'blockquote': 'blockquote'}
RICH_TEXT_HOLDERS = ('p', 'h2', 'li')
_BLANK_PARA = r'<p [^>]*>(?:\s|\xa0|<br>)*</p>'


class _Rich(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack, self.skip = [], [], 0

    def _open(self, tag, attrs=''):
        self.out.append(f'<{tag}{attrs} style="{RICH_STYLE[tag]}">' if tag in RICH_STYLE else f'<{tag}{attrs}>')
        self.stack.append(tag)

    def _close(self, tag):
        """Close the nearest open tag of this kind, and anything left open inside it."""
        while tag in self.stack:
            last = self.stack.pop()
            self.out.append(f'</{last}>')
            if last == tag:
                break

    def _holder(self):
        """Text always sits in a paragraph, a heading or a list item."""
        if not any(t in RICH_TEXT_HOLDERS for t in self.stack):
            self._open('p')

    def _list_level(self):
        return next((t for t in reversed(self.stack) if t in ('ul', 'ol', 'li')), None)

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        elif self.skip:
            return
        elif tag == 'br':
            self._holder()
            self.out.append('<br>')
        elif tag in RICH_INLINE:
            self._holder()
            self._open(RICH_INLINE[tag])
        elif tag == 'a':
            href = (dict(attrs).get('href') or '').strip()
            if 'a' not in self.stack and re.fullmatch(r'(?i)(https?://|mailto:)[^\s"<>]+', href):
                self._holder()
                self._open('a', f' href="{html.escape(href)}"')
        elif tag == 'li':
            if self._list_level() == 'li':
                self._close('li')
            if self._list_level():
                self._open('li')
        elif tag in RICH_BLOCK:
            kind = RICH_BLOCK[tag]
            if kind == 'p' and self._list_level() == 'li':          # a line inside a list item stays in the item
                return
            self._close('p')
            self._close('h2')
            self._open(kind)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        elif not self.skip:
            kind = RICH_INLINE.get(tag) or RICH_BLOCK.get(tag) or (tag if tag in ('a', 'li') else '')
            if kind:
                self._close(kind)

    def handle_data(self, data):
        if self.skip or (not data.strip() and not any(t in RICH_TEXT_HOLDERS for t in self.stack)):
            return
        self._holder()
        if 'a' in self.stack:
            self.out.append(html.escape(data, quote=False))
        else:                                                       # an address typed as text becomes a link, as in a plain message
            self.out.append(urlize(data, autoescape=True).replace('<a href=', f'<a style="{RICH_STYLE["a"]}" href='))


def clean_html(raw):
    """The compose editor's markup, rebuilt from the tags a message may use."""
    parser = _Rich()
    parser.feed(str(raw or '')[:MAX_BODY])
    parser.close()
    while parser.stack:
        parser.out.append(f'</{parser.stack.pop()}>')
    doc, before = ''.join(parser.out), None
    while doc != before:                                            # tags left with nothing in them
        before = doc
        doc = re.sub(r'<(p|h2|li|ul|ol|blockquote|strong|em|u|a)( [^>]*)?>\s*</\1>', '', doc)
    return re.sub(rf'^(?:{_BLANK_PARA})+|(?:{_BLANK_PARA})+$', '', doc)       # empty lines before and after the text


def html_to_text(doc):
    """The same message for mail programs that show text only, and for searching and quoting it here."""
    def link(m):
        href, label = html.unescape(m[1]), html.unescape(strip_tags(m[2])).strip()
        words = m[2].rstrip()
        return m[2] if not label or href.endswith(label) else f'{words} ({m[1]}){m[2][len(words):]}'
    doc = re.sub(r'(?s)<a [^>]*?href="([^"]*)"[^>]*>(.*?)</a>', link, doc)
    doc = re.sub(r'<li[^>]*>', '- ', doc)
    doc = re.sub(r'</(p|h2|ul|ol|blockquote)>', r'\g<0>\n', doc)
    return _clean_text(doc, is_html=True)


def body_parts(raw, rich=False):
    """(text, html) of a message being written. Only what the editor sends is read as markup; anything else is plain text."""
    if not rich:
        return raw, ''
    doc = clean_html(raw)
    return html_to_text(doc), doc


# ---------------------------------------------------------------- the template
def template_context(subject, body, greeting='', signoff='', body_html=''):
    return {'subject': subject, 'body': body, 'body_html': body_html, 'greeting': greeting.strip(), 'signoff': signoff.strip() or f'The {settings.SITE_NAME} team',
            'company': settings.SITE_INSTITUTION, 'reply_to': address()}


def preview_html(subject, body, greeting='', signoff='', logo_url='', rich=False):
    """The message as its recipient will see it, with the logo loaded from the site instead of from the e-mail."""
    text, doc = body_parts(body, rich)
    ctx = {'name': '', 'site_name': settings.SITE_NAME, 'site_full_name': settings.SITE_FULL_NAME, 'support_email': settings.LEGAL['contact_email'],
           'logo_cid': LOGO_CID, **template_context(subject, text, greeting, signoff, doc)}
    return render_to_string('emails/mailbox_message.html', ctx).replace(f'cid:{LOGO_CID}', logo_url)


# ---------------------------------------------------------------- sending
def compose(to, subject, body, user, greeting='', signoff='', parent=None, body_html=''):
    """Save an outgoing message and send it once the transaction commits. Returns the MailMessage."""
    host = (address().split('@')[-1] or 'localhost').strip()
    m = MailMessage.objects.create(
        direction=MailMessage.OUT, status=MailMessage.QUEUED, message_id=make_msgid(domain=host), in_reply_to=parent.message_id if parent else '',
        parent=parent, root=(parent.root or parent) if parent else None, from_name=settings.SITE_NAME, from_email=address(), to=', '.join(to),
        subject=subject[:255], body=body, body_html=clean_html(body_html) if body_html else '', greeting=greeting.strip()[:120], signoff=signoff.strip()[:120],
        is_read=True, sent_by=user, date=timezone.now())

    def deliver():
        try:
            msg = _message(to, '', m.subject, 'mailbox_message', template_context(m.subject, m.body, m.greeting, m.signoff, m.body_html))
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
def _clean_text(content, is_html=False):
    """Readable text only: HTML loses its markup, scripts and styles, and long runs of empty lines are closed up."""
    content = str(content or '')
    if is_html:
        content = re.sub(r'(?is)<(script|style|head).*?</\1>', ' ', content)
        content = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>|</li>', '\n', content)
        content = html.unescape(strip_tags(content))
    content = re.sub(r'[ \t\xa0]+\n', '\n', content.replace('\r\n', '\n').replace('\r', '\n'))
    return re.sub(r'\n{3,}', '\n\n', content).strip()[:MAX_BODY]


def _text_of(msg):
    """The readable text of a message: its plain part, or its HTML with the markup removed."""
    try:
        part = msg.get_body(preferencelist=('plain', 'html'))
        if part is None:
            return ''
        content = part.get_content()
        if not isinstance(content, str):
            content = content.decode('utf-8', 'replace')
        return _clean_text(content, part.get_content_type() == 'text/html')
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


def _keep(mid, sender, to, subject, body, attachments, date, in_reply_to):
    """Save one received message, joined to the conversation it answers."""
    name, addr = parseaddr(str(sender or ''))
    irt = str(in_reply_to or '').strip()[:255]
    parent = MailMessage.objects.filter(message_id=irt).first() if irt else None
    return MailMessage.objects.create(
        direction=MailMessage.IN, status=MailMessage.RECEIVED, message_id=mid, in_reply_to=irt, parent=parent, root=(parent.root or parent) if parent else None,
        from_name=name[:120], from_email=addr[:254].lower(), to=', '.join(to)[:2000], subject=(str(subject or '').strip() or '(no subject)')[:255],
        body=body, attachments=attachments, date=min(date, timezone.now()))


def store(raw):
    """Keep one message received over IMAP. Returns the MailMessage, or None if it is already here."""
    msg = email.message_from_bytes(raw, policy=policy.default)
    mid = (str(msg.get('Message-ID') or '').strip() or f'<{hashlib.sha1(raw).hexdigest()}@no-message-id>')[:255]
    if MailMessage.objects.filter(message_id=mid).exists():
        return None
    try:
        date = parsedate_to_datetime(str(msg.get('Date')))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        date = timezone.now()
    to = [a for _, a in getaddresses([str(v) for v in msg.get_all('To', [])]) if a]
    return _keep(mid, msg.get('From'), to, msg.get('Subject'), _text_of(msg), _attachments_of(msg), date, msg.get('In-Reply-To'))


def _fetch_imap(limit):
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


# ---- Resend: it has no IMAP, so received mail is read from its Receiving API
def _resend(path):
    req = urllib.request.Request(RESEND_API + path, headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}', 'Accept': 'application/json', 'User-Agent': 'xprism-mailbox/1.0'})
    with urllib.request.urlopen(req, timeout=settings.IMAP_TIMEOUT) as r:
        return json.loads(r.read().decode('utf-8'))


def _resend_id(item):
    return (str(item.get('message_id') or '').strip() or f'<resend-{item.get("id")}@resend>')[:255]


def store_resend(item):
    """Keep one e-mail as Resend's "retrieve received email" call describes it. Returns the MailMessage, or None if it is already here."""
    mid = _resend_id(item)
    if MailMessage.objects.filter(message_id=mid).exists():
        return None
    headers = {str(k).lower(): v for k, v in (item.get('headers') or {}).items()} if isinstance(item.get('headers'), dict) else {}
    try:
        date = datetime.datetime.fromisoformat(str(item.get('created_at')).replace('Z', '+00:00'))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
    except ValueError:
        date = timezone.now()
    body = _clean_text(item.get('text')) if item.get('text') else _clean_text(item.get('html'), is_html=True)
    files = [{'name': str(a.get('filename') or 'attachment')[:120], 'size': int(a.get('size') or 0)} for a in (item.get('attachments') or []) if isinstance(a, dict)][:30]
    to = [str(a) for a in (item.get('to') or [])]
    return _keep(mid, headers.get('from') or item.get('from'), to, item.get('subject'), body, files, date, headers.get('in-reply-to'))


def _fetch_resend(limit):
    new = 0
    try:
        listing = _resend(f'/emails/receiving?limit={max(1, min(limit, 100))}')
        known = set(MailMessage.objects.filter(message_id__in=[_resend_id(i) for i in listing.get('data') or []]).values_list('message_id', flat=True))
        for item in reversed(listing.get('data') or []):                # oldest first, so a reply finds the message it answers
            if _resend_id(item) not in known and item.get('id') and store_resend(_resend(f'/emails/receiving/{item["id"]}')):
                new += 1
    except urllib.error.HTTPError as e:
        log.exception('Could not fetch mail from Resend')
        if e.code in (401, 403):
            return new, 'Resend refused the API key for reading received mail. Create a key with full access and put it in RESEND_API_KEY.'
        return new, f'Resend answered with an error ({e.code}).'
    except Exception as e:
        log.exception('Could not fetch mail from Resend')
        return new, f'Could not reach Resend: {str(e)[:200]}'
    return new, ''


def fetch(limit=200):
    """Bring in mail that has arrived since the last check. Returns (number of new messages, error text or '')."""
    if not can_receive():
        return 0, 'Receiving is not set up: add RESEND_RECEIVE=true (with Resend) or IMAP_HOST to .env.'
    new, errors = 0, []
    for wanted, source in ((via_resend(), _fetch_resend), (via_imap(), _fetch_imap)):
        if wanted:
            n, error = source(limit)
            new += n
            if error:
                errors.append(error)
    return new, ' '.join(errors)


def webhook_is_genuine(headers, body):
    """Check Resend's signature on a webhook (the Svix scheme): HMAC-SHA256 of "id.timestamp.body" with the endpoint's secret."""
    secret = settings.RESEND_WEBHOOK_SECRET
    msg_id, stamp, given = headers.get('svix-id', ''), headers.get('svix-timestamp', ''), headers.get('svix-signature', '')
    if not (secret and msg_id and stamp.isdigit() and given):
        return False
    if abs(time.time() - int(stamp)) > 300:                             # an old request replayed later
        return False
    try:
        key = base64.b64decode(secret.split('_', 1)[-1])
    except (binascii.Error, ValueError):
        return False
    expected = base64.b64encode(hmac.new(key, f'{msg_id}.{stamp}.'.encode() + body, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(expected, part.split(',', 1)[-1]) for part in given.split() if part.startswith('v1,'))


def erase_for(address_):
    """Remove the mail to and from an address whose owner asked for their data to be deleted."""
    if address_:
        MailMessage.objects.filter(from_email__iexact=address_).delete()
        MailMessage.objects.filter(direction=MailMessage.OUT, to__iexact=address_).delete()
