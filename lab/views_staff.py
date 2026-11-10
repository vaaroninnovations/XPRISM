import csv
import io
from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AssignmentForm, BatchForm, GradeForm, StudentAddForm, UploadForm, make_username, temp_password
from .models import Assignment, Attempt, Batch, Enrollment, ExperimentFeedback, Role, User, new_class_code
from .permissions import (audit, batches_for, can_enrol, can_grade, can_manage_batch, get_assignment_or_403,
                          get_attempt_or_403, get_batch_or_403, role_required)

STAFF = (Role.FACULTY, Role.LAB_ASSISTANT, Role.COLLEGE_ADMIN)


def _college_for_new_batch(request):
    if request.user.college:
        return request.user.college
    raise PermissionDenied('Platform admins create batches from inside a college (use Django admin).')


@role_required(*STAFF)
def dashboard(request):
    bs = batches_for(request.user).filter(archived=False).annotate(n_students=Count('enrollments', distinct=True))
    to_grade = Attempt.objects.filter(assignment__batch__in=bs, status=Attempt.SUBMITTED).select_related('student', 'assignment__experiment', 'assignment__batch').order_by('submitted_at')
    upcoming = Assignment.objects.filter(batch__in=bs, due_at__gte=timezone.now()).select_related('experiment', 'batch').order_by('due_at')[:8]
    return render(request, 'lab/staff_dashboard.html', {'batches': bs, 'to_grade': to_grade[:15], 'n_to_grade': to_grade.count(), 'upcoming': upcoming})


@role_required(*STAFF)
def batch_list(request):
    show_archived = request.GET.get('archived') == '1'
    bs = batches_for(request.user).filter(archived=show_archived).annotate(n_students=Count('enrollments', distinct=True), n_assign=Count('assignments', distinct=True)).prefetch_related('faculty')
    return render(request, 'lab/batch_list.html', {'batches': bs, 'show_archived': show_archived,
                                                   'can_create': request.user.role in (Role.FACULTY, Role.COLLEGE_ADMIN)})


@role_required(Role.FACULTY, Role.COLLEGE_ADMIN)
def batch_form(request, pk=None):
    batch = get_batch_or_403(request.user, pk) if pk else None
    if batch and not can_manage_batch(request.user, batch):
        raise PermissionDenied
    college = batch.college if batch else _college_for_new_batch(request)
    form = BatchForm(request.POST or None, instance=batch, college=college)
    if request.method == 'POST' and form.is_valid():
        b = form.save(commit=False)
        if not batch:
            b.college, b.created_by = college, request.user
        b.save()
        form.save_m2m()
        if request.user.role == Role.FACULTY:
            b.faculty.add(request.user)
        audit(request, 'batch_saved', b, batch=b.pk)
        messages.success(request, f'Batch "{b.name}" saved. Class code: {b.class_code}')
        return redirect('batch_detail', b.pk)
    return render(request, 'lab/form_page.html', {'form': form, 'title': 'Edit batch' if batch else 'New batch', 'back': batch.get_absolute_url() if batch else '/faculty/batches/'})


@role_required(*STAFF)
def batch_detail(request, pk):
    b = get_batch_or_403(request.user, pk)
    enrolls = b.enrollments.select_related('student').order_by('student__roll_no', 'student__first_name')
    assigns = b.assignments.select_related('experiment').annotate(
        n_sub=Count('attempts', filter=~Q(attempts__status=Attempt.STARTED), distinct=True),
        n_grade=Count('attempts', filter=Q(attempts__status=Attempt.SUBMITTED), distinct=True))
    return render(request, 'lab/batch_detail.html', {
        'b': b, 'enrolls': enrolls, 'assigns': assigns, 'manage': can_manage_batch(request.user, b), 'enrol': can_enrol(request.user, b),
        'add_form': StudentAddForm(), 'upload_form': UploadForm(), 'join_url': request.build_absolute_uri(f'/accounts/signup/?code={b.class_code}')})


@require_POST
@role_required(*STAFF)
def batch_action(request, pk, action):
    b = get_batch_or_403(request.user, pk)
    if not can_manage_batch(request.user, b):
        raise PermissionDenied
    if action == 'regen':
        b.class_code = new_class_code(); b.save(); messages.success(request, f'New class code: {b.class_code}')
    elif action == 'toggle_join':
        b.join_enabled = not b.join_enabled; b.save(); messages.success(request, f'Joining with class code {"enabled" if b.join_enabled else "disabled"}.')
    elif action == 'archive':
        b.archived = not b.archived; b.save(); messages.success(request, 'Batch archived.' if b.archived else 'Batch restored.')
    audit(request, f'batch_{action}', b, batch=b.pk)
    return redirect('batch_detail', b.pk)


def _get_or_create_student(college, roll, first, last, email):
    username = make_username(college, roll)
    u = User.objects.filter(username=username).first()
    if u:
        if u.role != Role.STUDENT or u.college_id != college.pk:
            return None, None, f'username {username} belongs to another account'
        return u, None, None
    pw = temp_password()
    u = User(username=username, first_name=first, last_name=last or '', email=email or '', role=Role.STUDENT, college=college, roll_no=roll, must_change_password=True)
    u.set_password(pw)
    u.save()
    return u, pw, None


@require_POST
@role_required(*STAFF)
def student_add(request, pk):
    b = get_batch_or_403(request.user, pk)
    if not can_enrol(request.user, b):
        raise PermissionDenied
    form = StudentAddForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please fill in first name and roll number.')
        return redirect('batch_detail', b.pk)
    cd = form.cleaned_data
    u, pw, err = _get_or_create_student(b.college, cd['roll_no'], cd['first_name'], cd['last_name'], cd['email'])
    if err:
        messages.error(request, err)
    else:
        Enrollment.objects.get_or_create(batch=b, student=u, defaults={'via': 'faculty'})
        audit(request, 'student_added', u.username, batch=b.pk)
        messages.success(request, f'{u.display_name} enrolled. Username: {u.username}' + (f' • Temporary password: {pw} (must be changed at first sign-in)' if pw else ' (existing account)'))
    return redirect('batch_detail', b.pk)


def _read_rows(f):
    name = f.name.lower()
    if name.endswith('.xlsx'):
        from openpyxl import load_workbook
        ws = load_workbook(f, read_only=True, data_only=True).active
        rows = [[('' if c is None else str(c)).strip() for c in r] for r in ws.iter_rows(values_only=True)]
    else:
        text = f.read().decode('utf-8-sig', errors='replace')
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    head = [h.lower().replace(' ', '_').replace('.', '') for h in rows[0]]
    alias = {'roll': 'roll_no', 'rollno': 'roll_no', 'roll_number': 'roll_no', 'enrolment_no': 'roll_no', 'enrollment_no': 'roll_no',
             'first': 'first_name', 'firstname': 'first_name', 'name': 'first_name', 'last': 'last_name', 'lastname': 'last_name', 'surname': 'last_name', 'e-mail': 'email', 'mail': 'email'}
    head = [alias.get(h, h) for h in head]
    if 'roll_no' not in head or 'first_name' not in head:
        raise ValueError('The first row must contain headings including roll_no and first_name.')
    return [dict(zip(head, r)) for r in rows[1:]]


@require_POST
@role_required(*STAFF)
def students_upload(request, pk):
    b = get_batch_or_403(request.user, pk)
    if not can_enrol(request.user, b):
        raise PermissionDenied
    form = UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, ' '.join(sum(form.errors.values(), [])))
        return redirect('batch_detail', b.pk)
    try:
        rows = _read_rows(form.cleaned_data['file'])
    except Exception as e:  # malformed spreadsheet
        messages.error(request, f'Could not read the file: {e}')
        return redirect('batch_detail', b.pk)
    if len(rows) > 500:
        messages.error(request, 'Maximum 500 students per upload.')
        return redirect('batch_detail', b.pk)
    created, existing, errors, creds = 0, 0, [], []
    with transaction.atomic():
        for i, r in enumerate(rows, start=2):
            roll, first = r.get('roll_no', ''), r.get('first_name', '')
            if not roll or not first:
                errors.append(f'row {i}: roll_no and first_name are required'); continue
            u, pw, err = _get_or_create_student(b.college, roll, first, r.get('last_name', ''), r.get('email', ''))
            if err:
                errors.append(f'row {i}: {err}'); continue
            Enrollment.objects.get_or_create(batch=b, student=u, defaults={'via': 'csv'})
            if pw:
                created += 1; creds.append([roll, u.display_name, u.username, pw])
            else:
                existing += 1
    request.session['cred_sheet'] = {'batch': b.name, 'rows': creds}
    audit(request, 'students_uploaded', b, batch=b.pk, created=created, existing=existing, errors=len(errors))
    messages.success(request, f'{created} new student account(s) created, {existing} existing account(s) enrolled.' + (f' {len(errors)} row(s) skipped: ' + '; '.join(errors[:5]) if errors else ''))
    if creds:
        messages.warning(request, 'Download the credentials sheet now: it is shown only once.')
    return redirect('batch_detail', b.pk)


@role_required(*STAFF)
def credentials_download(request, pk):
    get_batch_or_403(request.user, pk)
    sheet = request.session.pop('cred_sheet', None)
    if not sheet:
        messages.error(request, 'The credentials sheet has already been downloaded. Reset individual passwords if needed.')
        return redirect('batch_detail', pk)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['roll_no', 'name', 'username', 'temporary_password'])
    w.writerows(sheet['rows'])
    resp = HttpResponse(out.getvalue(), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="student-credentials.csv"'
    return resp


@require_POST
@role_required(*STAFF)
def student_action(request, pk, user_id, action):
    b = get_batch_or_403(request.user, pk)
    if not can_enrol(request.user, b):
        raise PermissionDenied
    e = get_object_or_404(Enrollment, batch=b, student_id=user_id)
    s = e.student
    if action == 'remove':
        e.delete(); messages.success(request, f'{s.display_name} removed from this batch (account kept).')
    elif action == 'reset':
        pw = temp_password(); s.set_password(pw); s.must_change_password = True; s.locked_until = None; s.failed_logins = 0; s.save()
        messages.success(request, f'Temporary password for {s.username}: {pw} (must be changed at next sign-in)')
    audit(request, f'student_{action}', s.username, batch=b.pk)
    return redirect('batch_detail', b.pk)


# ------------------------------------------------------------------ assignments & grading
@role_required(Role.FACULTY, Role.COLLEGE_ADMIN)
def assignment_form(request, batch_pk=None, pk=None):
    a = get_assignment_or_403(request.user, pk) if pk else None
    b = a.batch if a else get_batch_or_403(request.user, batch_pk)
    if not can_manage_batch(request.user, b):
        raise PermissionDenied
    form = AssignmentForm(request.POST or None, instance=a, college=b.college)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not a:
            obj.batch, obj.created_by = b, request.user
        obj.save()
        audit(request, 'assignment_saved', obj, batch=b.pk, exam=obj.exam_mode)
        messages.success(request, f'Assignment saved: {obj.experiment.title}, due {timezone.localtime(obj.due_at):%d %b %Y %H:%M}.')
        return redirect('batch_detail', b.pk)
    return render(request, 'lab/form_page.html', {'form': form, 'title': ('Edit assignment' if a else 'New assignment') + f' • {b.name}', 'back': b.get_absolute_url(),
                                                  'help': 'Exam mode hides the reference dataset, auto-run, assistant and skip buttons, and enforces the time limit from the moment the student opens the experiment.'})


@require_POST
@role_required(Role.FACULTY, Role.COLLEGE_ADMIN)
def assignment_delete(request, pk):
    a = get_assignment_or_403(request.user, pk)
    if not can_manage_batch(request.user, a.batch):
        raise PermissionDenied
    if a.attempts.exclude(status=Attempt.STARTED).exists():
        messages.error(request, 'Students have already submitted this assignment; it cannot be deleted.')
        return redirect('assignment_detail', a.pk)
    b = a.batch
    audit(request, 'assignment_deleted', a, batch=b.pk)
    a.delete()
    messages.success(request, 'Assignment deleted.')
    return redirect('batch_detail', b.pk)


@role_required(*STAFF)
def assignment_detail(request, pk):
    a = get_assignment_or_403(request.user, pk)
    students = [e.student for e in a.batch.enrollments.select_related('student').order_by('student__roll_no')]
    by_student = defaultdict(list)
    for at in a.attempts.select_related('student').order_by('started_at'):
        by_student[at.student_id].append(at)
    rows = []
    for s in students:
        ats = by_student.get(s.pk, [])
        done = [x for x in ats if x.status != Attempt.STARTED]
        best = max(done, key=lambda x: x.final_marks if x.final_marks is not None else -1, default=None)
        rows.append({'s': s, 'attempts': ats, 'best': best, 'in_progress': any(x.status == Attempt.STARTED for x in ats)})
    # viva item analysis (questions the batch got wrong most often)
    items = defaultdict(lambda: [0, 0, ''])
    for at in a.attempts.exclude(status=Attempt.STARTED):
        for it in (at.payload.get('viva') or {}).get('items') or []:
            k = it.get('i')
            items[k][1] += 1
            items[k][0] += 0 if it.get('ok') else 1
            items[k][2] = it.get('q', '')[:160]
    analysis = sorted([{'i': k, 'wrong': v[0], 'n': v[1], 'pct': round(v[0] / v[1] * 100) if v[1] else 0, 'q': v[2]} for k, v in items.items()], key=lambda x: -x['pct'])
    subs = [r['best'] for r in rows if r['best']]
    stats = {'n': len(students), 'submitted': len(subs), 'graded': sum(1 for r in subs if r.status == Attempt.GRADED),
             'mean': round(sum(x.final_marks for x in subs if x.final_marks is not None) / len(subs), 1) if subs else None}
    return render(request, 'lab/assignment_detail.html', {'a': a, 'rows': rows, 'analysis': analysis[:10], 'stats': stats,
                                                          'manage': can_manage_batch(request.user, a.batch), 'grade': can_grade(request.user, a.batch)})


@role_required(*STAFF)
def attempt_detail(request, pk):
    at = get_attempt_or_403(request.user, pk)
    a = at.assignment
    allowed = can_grade(request.user, a.batch)
    form = GradeForm(request.POST or None, max_marks=a.max_marks, initial={'manual_marks': at.manual_marks, 'feedback': at.feedback})
    if request.method == 'POST':
        if not allowed:
            raise PermissionDenied
        if at.status == Attempt.STARTED:
            messages.error(request, 'The student has not submitted this attempt yet.')
        elif form.is_valid():
            at.manual_marks = form.cleaned_data['manual_marks']
            at.feedback = form.cleaned_data['feedback']
            at.status, at.graded_by, at.graded_at = Attempt.GRADED, request.user, timezone.now()
            at.save()
            audit(request, 'attempt_graded', f'attempt {at.pk}', marks=str(at.final_marks))
            messages.success(request, f'Graded {at.student.display_name}: {at.final_marks}/{a.max_marks}.')
            nxt = a.attempts.filter(status=Attempt.SUBMITTED).exclude(pk=at.pk).order_by('submitted_at').first()
            return redirect('attempt_detail', nxt.pk) if nxt and request.POST.get('next') == '1' else redirect('assignment_detail', a.pk)
    return render(request, 'lab/attempt_detail.html', {'at': at, 'a': a, 'form': form, 'can_grade': allowed, 'payload': at.payload})


def _marks_matrix(b):
    assigns = list(b.assignments.select_related('experiment').order_by('due_at'))
    students = [e.student for e in b.enrollments.select_related('student').order_by('student__roll_no', 'student__first_name')]
    best = {}
    for at in Attempt.objects.filter(assignment__batch=b).exclude(status=Attempt.STARTED).select_related('assignment'):
        k = (at.student_id, at.assignment_id)
        if at.final_marks is not None and (k not in best or at.final_marks > best[k].final_marks):
            best[k] = at
    rows = []
    for s in students:
        cells = [best.get((s.pk, a.pk)) for a in assigns]
        total = sum(c.final_marks for c in cells if c and c.final_marks is not None)
        rows.append({'s': s, 'cells': cells, 'total': round(total, 1)})
    return assigns, rows, round(sum(float(a.max_marks) for a in assigns), 1)


@role_required(*STAFF)
def marks_sheet(request, pk):
    b = get_batch_or_403(request.user, pk)
    assigns, rows, max_total = _marks_matrix(b)
    fmt = request.GET.get('format')
    if fmt in ('csv', 'xlsx'):
        if request.user.role == Role.LAB_ASSISTANT:
            raise PermissionDenied
        head = ['Roll no', 'Name', 'Username'] + [f'Exp {a.experiment.no:02d} (/{a.max_marks})' for a in assigns] + [f'Total (/{max_total})']
        data = [[r['s'].roll_no, r['s'].display_name, r['s'].username] + [(c.final_marks if c else '') for c in r['cells']] + [r['total']] for r in rows]
        audit(request, 'marks_exported', b, batch=b.pk, format=fmt)
        fname = f'marks-{b.name}-{b.academic_year}'.replace(' ', '_').replace(',', '').replace('/', '-')
        if fmt == 'csv':
            out = io.StringIO(); w = csv.writer(out); w.writerow([f'{b.college.name} • {b.name} • {b.academic_year}']); w.writerow(head); w.writerows(data)
            resp = HttpResponse(out.getvalue(), content_type='text/csv')
            resp['Content-Disposition'] = f'attachment; filename="{fname}.csv"'
            return resp
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        wb = Workbook(); ws = wb.active; ws.title = 'Marks'
        ws.append([f'{b.college.name} • {b.name} • {b.academic_year} • exported {timezone.localtime():%d %b %Y %H:%M}'])
        ws['A1'].font = Font(bold=True, size=12)
        ws.append(head)
        for c in ws[2]:
            c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='0D9488'); c.alignment = Alignment(wrap_text=True, horizontal='center')
        for row in data:
            ws.append(row)
        ws.column_dimensions['A'].width = 14; ws.column_dimensions['B'].width = 26; ws.column_dimensions['C'].width = 22
        ws.freeze_panes = 'D3'
        buf = io.BytesIO(); wb.save(buf)
        resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{fname}.xlsx"'
        return resp
    return render(request, 'lab/marks_sheet.html', {'b': b, 'assigns': assigns, 'rows': rows, 'max_total': max_total, 'can_export': request.user.role != Role.LAB_ASSISTANT})


@role_required(Role.FACULTY, Role.LAB_ASSISTANT, Role.COLLEGE_ADMIN)
def feedback_overview(request):
    """What students said about each experiment. No names: the form promises that."""
    u = request.user
    qs = ExperimentFeedback.objects.all() if u.is_platform_admin else ExperimentFeedback.objects.filter(college=u.college)
    rows = list(qs.values('experiment__no', 'experiment__title').annotate(
        n=Count('pk'), avg=Avg('rating'), easy=Count('pk', filter=Q(difficulty=ExperimentFeedback.EASY)),
        right=Count('pk', filter=Q(difficulty=ExperimentFeedback.RIGHT)), hard=Count('pk', filter=Q(difficulty=ExperimentFeedback.HARD))).order_by('experiment__no'))
    total = sum(r['n'] for r in rows)
    overall = round(sum(r['avg'] * r['n'] for r in rows) / total, 1) if total else None
    for r in rows:
        r['avg'] = round(r['avg'], 1)
        r['pct'] = round(r['avg'] / 5 * 100)
    comments = qs.exclude(comment='').select_related('experiment')[:60]
    return render(request, 'lab/feedback_overview.html', {'rows': rows, 'total': total, 'overall': overall, 'comments': comments,
                                                           'lowest': min(rows, key=lambda r: r['avg']) if len(rows) > 1 else None})
