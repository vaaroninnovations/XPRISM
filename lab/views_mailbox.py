"""The super admins' mailbox pages: folders, reading a conversation, writing and replying."""
from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import mailbox
from .forms import MailComposeForm
from .models import MailMessage, Role
from .permissions import audit, role_required

platform = role_required(Role.SUPERADMIN)
FOLDERS = [('inbox', 'Inbox'), ('starred', 'Starred'), ('sent', 'Sent'), ('archive', 'Archive'), ('trash', 'Trash')]
AUTO_CHECK_SECONDS = 300


def _in_folder(folder):
    live = MailMessage.objects.filter(trashed_at__isnull=True)
    return {
        'inbox': live.filter(direction=MailMessage.IN, archived=False),
        'starred': live.filter(starred=True),
        'sent': live.filter(direction=MailMessage.OUT, archived=False),
        'archive': live.filter(archived=True),
        'trash': MailMessage.objects.filter(trashed_at__isnull=False),
    }[folder]


def _counts():
    return {'inbox': _in_folder('inbox').filter(is_read=False).count(), 'failed': _in_folder('sent').filter(status=MailMessage.FAILED).count(),
            'trash': _in_folder('trash').count()}


def _check(request, quiet=False):
    new, error = mailbox.fetch()
    if error and not (quiet and not mailbox.can_receive()):
        messages.error(request, error)
    elif new:
        messages.success(request, f'{new} new message{"s" if new != 1 else ""}.')
    elif not quiet:
        messages.info(request, 'No new mail.')
    return new


ACTIONS = {
    'read': {'is_read': True}, 'unread': {'is_read': False}, 'star': {'starred': True}, 'unstar': {'starred': False},
    'archive': {'archived': True}, 'unarchive': {'archived': False}, 'restore': {'trashed_at': None},
}


def _act(request, action, ids):
    """Apply one action to the chosen messages. Returns the text to show, or '' if nothing was done."""
    qs = MailMessage.objects.filter(pk__in=ids)
    if action in ACTIONS:
        n = qs.update(**ACTIONS[action])
    elif action == 'trash':
        n = qs.filter(trashed_at__isnull=True).update(trashed_at=timezone.now())
    elif action == 'delete':                                    # for good, and only from the trash
        n = qs.filter(trashed_at__isnull=False).count()
        qs.filter(trashed_at__isnull=False).delete()
    else:
        return ''
    if n and action in ('trash', 'delete', 'restore'):
        audit(request, f'mail_{action}', f'{n} message{"s" if n != 1 else ""}')
    words = {'read': 'marked as read', 'unread': 'marked as unread', 'star': 'starred', 'unstar': 'unstarred', 'archive': 'archived',
             'unarchive': 'moved back', 'restore': 'restored', 'trash': 'moved to the trash', 'delete': 'deleted for good'}
    return f'{n} message{"s" if n != 1 else ""} {words[action]}.' if n else ''


@platform
def mailbox_list(request):
    folder = request.GET.get('folder', 'inbox')
    if folder not in dict(FOLDERS):
        folder = 'inbox'
    if request.method == 'POST':
        action = request.POST.get('action', '')
        star = request.POST.get('toggle_star', '')
        if star.isdigit():                                      # the star beside one message
            m = MailMessage.objects.filter(pk=int(star)).first()
            if m:
                MailMessage.objects.filter(pk=m.pk).update(starred=not m.starred)
        elif action == 'check':
            _check(request)
        elif action == 'empty_trash':
            n = _in_folder('trash').count()
            _in_folder('trash').delete()
            if n:
                audit(request, 'mail_delete', f'{n} messages (trash emptied)')
                messages.success(request, f'Trash emptied: {n} message{"s" if n != 1 else ""} deleted for good.')
        else:
            ids = [int(i) for i in request.POST.getlist('ids') if i.isdigit()]
            text = _act(request, action, ids) if ids else ''
            if text:
                messages.success(request, text)
            elif action:
                messages.info(request, 'Choose one or more messages first.')
        back = request.POST.get('back', '')
        return redirect(back if back.startswith(reverse('mailbox')) else reverse('mailbox'))
    if folder == 'inbox' and mailbox.can_receive() and cache.add('mailbox-auto-check', 1, AUTO_CHECK_SECONDS):
        _check(request, quiet=True)
    q = request.GET.get('q', '').strip()
    qs = _in_folder(folder)
    if q:
        qs = qs.filter(Q(subject__icontains=q) | Q(from_email__icontains=q) | Q(from_name__icontains=q) | Q(to__icontains=q) | Q(body__icontains=q))
    page = Paginator(qs.select_related('sent_by'), 25).get_page(request.GET.get('page'))
    return render(request, 'lab/mailbox.html', {
        'folder': folder, 'folder_name': dict(FOLDERS)[folder], 'folders': FOLDERS, 'counts': _counts(), 'page': page, 'q': q,
        'can_receive': mailbox.can_receive(), 'can_send': mailbox.can_send(), 'address': mailbox.address()})


@platform
def mailbox_message(request, pk):
    m = get_object_or_404(MailMessage, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'resend' and m.direction == MailMessage.OUT and m.status == MailMessage.FAILED:
            if not mailbox.can_send():
                messages.error(request, 'Sending is not set up: add EMAIL_HOST to .env.')
            else:
                with transaction.atomic():
                    again = mailbox.compose(m.recipients, m.subject, m.body, request.user, m.greeting, m.signoff, m.parent)
                    m.delete()
                    audit(request, 'mail_sent', f'#{again.pk} (sent again)', to=again.to)
                messages.success(request, 'Sent again.')
                return redirect('mailbox_message', pk=again.pk)
        else:
            text = _act(request, action, [m.pk])
            if text:
                messages.success(request, text.replace('1 message', 'Message'))
            if action in ('trash', 'delete', 'archive', 'unread'):
                return redirect(reverse('mailbox') + (f'?folder={request.POST.get("folder")}' if request.POST.get('folder') in dict(FOLDERS) else ''))
        return redirect('mailbox_message', pk=m.pk) if MailMessage.objects.filter(pk=m.pk).exists() else redirect('mailbox')
    root = m.root or m
    thread = list(MailMessage.objects.filter(Q(pk=root.pk) | Q(root=root)).select_related('sent_by').order_by('date', 'pk'))
    unread = [t.pk for t in thread if not t.is_read]
    if unread:
        MailMessage.objects.filter(pk__in=unread).update(is_read=True)
    folder = request.GET.get('folder') if request.GET.get('folder') in dict(FOLDERS) else ('trash' if m.trashed_at else 'archive' if m.archived else 'sent' if m.direction == MailMessage.OUT else 'inbox')
    return render(request, 'lab/mailbox_message.html', {
        'm': m, 'thread': thread, 'folder': folder, 'folder_name': dict(FOLDERS)[folder], 'folders': FOLDERS, 'counts': _counts(), 'can_send': mailbox.can_send(),
        'can_receive': mailbox.can_receive()})


def _quote(m):
    who = m.from_name or m.from_email or settings.SITE_NAME
    lines = '\n'.join('> ' + line for line in m.body.splitlines()[:60])
    return f'\n\n\nOn {timezone.localtime(m.date):%d %b %Y, %H:%M}, {who} wrote:\n{lines}'


@platform
def mailbox_compose(request):
    parent = None
    ref = request.POST.get('parent') or request.GET.get('reply') or ''
    if ref.isdigit():
        parent = MailMessage.objects.filter(pk=int(ref)).first()
    if request.method == 'POST':
        form = MailComposeForm(request.POST)
        if not mailbox.can_send():
            form.add_error(None, 'Sending is not set up yet: add EMAIL_HOST and its password to .env, then restart the site.')
        elif form.is_valid():
            cd = form.cleaned_data
            left = settings.MAILBOX_MAX_PER_DAY - mailbox.sent_today()
            if left <= 0:
                form.add_error(None, f'The limit of {settings.MAILBOX_MAX_PER_DAY} messages in 24 hours has been reached. Try again later.')
            else:
                with transaction.atomic():
                    m = mailbox.compose(cd['to'], cd['subject'], cd['body'], request.user, cd['greeting'], cd['signoff'], parent)
                    audit(request, 'mail_sent', f'#{m.pk}', to=m.to, subject=m.subject[:80])
                messages.success(request, f'Message sent to {m.to}.')
                return redirect('mailbox_message', pk=m.pk)
    else:
        initial = {'signoff': f'The {settings.SITE_NAME} team', 'to': request.GET.get('to', '')[:300]}
        forward = request.GET.get('forward', '')
        if parent:
            subject = parent.subject if parent.subject.lower().startswith('re:') else f'Re: {parent.subject}'
            initial.update(to=parent.from_email if parent.direction == MailMessage.IN else parent.to, subject=subject[:255], greeting=parent.from_name if parent.direction == MailMessage.IN else '', body=_quote(parent))
        elif forward.isdigit():
            src = MailMessage.objects.filter(pk=int(forward)).first()
            if src:
                subject = src.subject if src.subject.lower().startswith('fwd:') else f'Fwd: {src.subject}'
                initial.update(subject=subject[:255], body=f'\n\n\nForwarded message from {src.from_name or src.from_email or settings.SITE_NAME}, {timezone.localtime(src.date):%d %b %Y, %H:%M}:\n\n{src.body[:20000]}')
        form = MailComposeForm(initial=initial)
    return render(request, 'lab/mailbox_compose.html', {
        'form': form, 'parent': parent, 'folder': '', 'folders': FOLDERS, 'counts': _counts(), 'can_send': mailbox.can_send(), 'can_receive': mailbox.can_receive(),
        'address': mailbox.address(), 'left_today': max(0, settings.MAILBOX_MAX_PER_DAY - mailbox.sent_today()), 'max_recipients': mailbox.MAX_RECIPIENTS})


@platform
@require_POST
def mailbox_preview(request):
    """The message in the e-mail template, for the preview beside the compose form."""
    p = request.POST
    doc = mailbox.preview_html(p.get('subject', '')[:255], p.get('body', '')[:mailbox.MAX_BODY], p.get('greeting', '')[:120], p.get('signoff', '')[:120],
                               staticfiles_storage.url('img/xprism-lockup.png'))
    return JsonResponse({'html': doc})


@csrf_exempt
@require_POST
def resend_inbound(request):
    """Resend calls this when an e-mail arrives. The call only says "look now": the mail itself is then read from
    Resend with the API key, so nothing in the request body is trusted or stored."""
    if not (settings.RESEND_WEBHOOK_SECRET and mailbox.via_resend()):
        raise Http404
    if not mailbox.webhook_is_genuine(request.headers, request.body):
        return JsonResponse({'error': 'Signature not valid.'}, status=401)
    new, error = mailbox.fetch()
    return JsonResponse({'ok': not error, 'new': new}, status=502 if error else 200)
