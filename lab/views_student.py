import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import access
from .feedback import attempt_report
from .models import Assignment, Attempt, Experiment, ExperimentFeedback, Role
from .permissions import audit, get_attempt_or_403, role_required


def _summary(a, attempts):
    done = [x for x in attempts if x.status != Attempt.STARTED]
    best = max(done, key=lambda x: (x.final_marks if x.final_marks is not None else -1), default=None)
    if best and best.status == Attempt.GRADED:
        state = 'graded'
    elif best:
        state = 'submitted'
    elif any(x.status == Attempt.STARTED for x in attempts):
        state = 'in_progress'
    elif timezone.now() < a.opens_at:
        state = 'upcoming'
    elif a.is_overdue:
        state = 'overdue'
    else:
        state = 'open'
    return {'a': a, 'attempts': attempts, 'best': best, 'state': state, 'used': len(done), 'can_start': len(done) < a.max_attempts and a.is_open and timezone.now() >= a.opens_at}


@role_required(Role.STUDENT)
def dashboard(request):
    u = request.user
    access.consume_open(u, 'dashboard')
    assigns = Assignment.objects.filter(batch__enrollments__student=u, batch__archived=False).select_related('experiment', 'batch').order_by('due_at')
    mine = {}
    for at in Attempt.objects.filter(student=u).select_related('assignment'):
        mine.setdefault(at.assignment_id, []).append(at)
    rows = [_summary(a, mine.get(a.pk, [])) for a in assigns]
    batches = [e.batch for e in u.enrollments.select_related('batch')]
    scored = [r['best'].final_marks / float(r['a'].max_marks) * 100 for r in rows if r['best'] and r['best'].final_marks is not None]
    return render(request, 'lab/student_dashboard.html', {
        'todo': [r for r in rows if r['state'] in ('open', 'in_progress', 'overdue', 'upcoming')],
        'done': [r for r in rows if r['state'] in ('submitted', 'graded')],
        'batches': batches, 'avg': round(sum(scored) / len(scored), 1) if scored else None})


@role_required(Role.STUDENT)
def assignment(request, pk):
    a = get_object_or_404(Assignment.objects.select_related('experiment', 'batch'), pk=pk, batch__enrollments__student=request.user)
    attempts = list(Attempt.objects.filter(assignment=a, student=request.user))
    ctx = _summary(a, attempts)
    latest = next((x for x in attempts if x.status != Attempt.STARTED), None)       # attempts are newest first
    ctx.update(latest=latest, report=attempt_report(latest) if latest else None, can_rate=not request.user.is_shared_demo,
               rated=bool(latest) and ExperimentFeedback.objects.filter(attempt=latest).exists())
    return render(request, 'lab/student_assignment.html', ctx)


def _clip(obj, limit=60000):
    s = json.dumps(obj, default=str)
    return obj if len(s) <= limit else {'truncated': True, 'text': s[:limit]}


@require_POST
def api_submit(request, pk):
    """Called by bridge.js when a student presses 'Submit to faculty'."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Your session has expired. Sign in again in a new tab, then submit.'}, status=401)
    if request.user.role != Role.STUDENT:
        return JsonResponse({'error': 'Only students submit attempts.'}, status=403)
    at = get_attempt_or_403(request.user, pk)
    if at.status != Attempt.STARTED:
        return JsonResponse({'error': 'This attempt has already been submitted.'}, status=409)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid data.'}, status=400)
    now = timezone.now()
    a = at.assignment
    if at.deadline and now > at.deadline + timezone.timedelta(minutes=2):
        at.timed_out = True
    viva = data.get('viva') or {}
    try:
        vs, vt = int(viva.get('score')), int(viva.get('total'))
        if 0 <= vs <= vt <= 100:
            at.viva_score, at.viva_total = vs, vt
    except (TypeError, ValueError):
        pass
    ans = data.get('answer') or {}
    given, truth = str(ans.get('given') or '')[:120], ans.get('truth')
    if given != '' and truth not in (None, ''):
        at.answer_given, at.answer_true = given, str(truth)[:120]
        if ans.get('kind') == 'number':
            try:
                g, t, tol = float(given), float(truth), float(ans.get('tol') or 5)
                at.answer_ok = abs(g - t) / abs(t) * 100 <= tol if t else g == t
            except ValueError:
                at.answer_ok = False
        else:
            at.answer_ok = given == str(truth)
    elif truth not in (None, ''):
        at.answer_true, at.answer_ok = str(truth)[:120], False     # question existed but was not answered
    at.completion = bool(data.get('completion'))
    at.payload = _clip({k: data.get(k) for k in ('results', 'tables', 'inference', 'viva', 'inputs', 'notes', 'client') if data.get(k) is not None})
    at.submitted_at = now
    at.is_late = now > a.due_at
    at.status = Attempt.SUBMITTED
    at.compute_auto_score()
    at.save()
    audit(request, 'attempt_submitted', f'attempt {at.pk}', exp=a.experiment.no, auto=at.auto_score)
    return JsonResponse({'ok': True, 'auto_score': at.auto_score, 'marks': at.final_marks, 'max_marks': float(a.max_marks),
                         'viva': [at.viva_score, at.viva_total], 'answer_ok': at.answer_ok, 'late': at.is_late, 'timed_out': at.timed_out,
                         'report': attempt_report(at)})


@require_POST
def api_feedback(request, slug):
    """Called by bridge.js and the assignment page when a student rates an experiment."""
    u = request.user
    if not u.is_authenticated:
        return JsonResponse({'error': 'Your session has expired. Sign in again, then send your feedback.'}, status=401)
    if u.role != Role.STUDENT:
        return JsonResponse({'error': 'Only students and free-trial users rate experiments.'}, status=403)
    exp = get_object_or_404(Experiment, slug=slug)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
        rating = int(data.get('rating'))
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Choose a rating from 1 to 5.'}, status=400)
    if not 1 <= rating <= 5:
        return JsonResponse({'error': 'Choose a rating from 1 to 5.'}, status=400)
    difficulty = data.get('difficulty') if data.get('difficulty') in dict(ExperimentFeedback.DIFFICULTY) else ''
    comment = str(data.get('comment') or '').strip()[:1000]
    attempt = None
    if data.get('attempt') not in (None, ''):
        ref = str(data['attempt'])
        attempt = Attempt.objects.filter(pk=int(ref) if ref.isdigit() else 0, student=u, assignment__experiment=exp).exclude(status=Attempt.STARTED).first()
        if attempt is None:
            return JsonResponse({'error': 'Submit the attempt before you rate it.'}, status=400)
    context = ExperimentFeedback.ASSIGNMENT if attempt else (ExperimentFeedback.PRACTICE if u.has_full_access else ExperimentFeedback.TRIAL)
    values = {'rating': rating, 'difficulty': difficulty, 'comment': comment, 'college': u.college, 'context': context}
    if attempt:
        ExperimentFeedback.objects.update_or_create(attempt=attempt, defaults={**values, 'user': u, 'experiment': exp})
    else:
        ExperimentFeedback.objects.update_or_create(user=u, experiment=exp, attempt=None, defaults=values)
    audit(request, 'experiment_feedback', f'exp {exp.no}', rating=rating)
    return JsonResponse({'ok': True})
