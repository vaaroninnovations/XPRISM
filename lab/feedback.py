"""The feedback report a student sees after submitting: what each part of the automatic score earned, and what to revise."""
from .models import Attempt


def _clean(text):
    return str(text or '').strip()


def attempt_report(at):
    """A plain dict, used as JSON by bridge.js and by the assignment page. Mirrors Attempt.compute_auto_score()."""
    from .views_public import EXP_PROBES        # imported here: views_public imports the models this module needs
    a = at.assignment
    exam = a.exam_mode
    viva = (at.payload or {}).get('viva') or {}
    parts = []
    if at.viva_total:
        missed = at.viva_total - at.viva_score
        unanswered = viva.get('answered') == 0
        if unanswered:
            advice = 'The viva was not answered. Open the viva on the bench and answer every question before you submit.'
        elif not missed:
            advice = 'Every viva question is right.'
        elif exam:
            advice = f'{missed} question{"s" if missed != 1 else ""} missed. In exam mode the answers stay hidden: go through them with your faculty.'
        else:
            advice = f'{missed} question{"s" if missed != 1 else ""} missed. Revise {"them" if missed != 1 else "it"} below.'
        parts.append({'key': 'viva', 'label': 'Viva', 'weight': 40, 'fraction': at.viva_score / at.viva_total, 'value': f'{at.viva_score}/{at.viva_total}', 'advice': advice})
    if at.answer_ok is not None:
        numeric = (EXP_PROBES.get(a.experiment.no) or ('', '', 'choice', 0))[2] == 'number'
        if at.answer_ok:
            value, advice = 'Correct', 'Your value for the unknown is within the accepted range.' if numeric else 'You identified the unknown correctly.'
        elif not at.answer_given:
            value, advice = 'Not entered', 'No answer was entered for the unknown. Enter your value or deduction before you submit.'
        elif numeric:
            value, advice = 'Out of range', 'Your value for the unknown is outside the accepted range. Recheck your readings, then the calculation.'
        else:
            value, advice = 'Not right', 'Your deduction for the unknown is not right. Compare its responses with the standards again.'
        parts.append({'key': 'answer', 'label': 'Unknown', 'weight': 30, 'fraction': 1.0 if at.answer_ok else 0.0, 'value': value, 'advice': advice})
    parts.append({'key': 'observations', 'label': 'Observation sheet', 'weight': 30, 'fraction': 1.0 if at.completion else 0.0,
                  'value': 'Complete' if at.completion else 'Incomplete',
                  'advice': 'Your readings are recorded.' if at.completion else 'The observation sheet was empty or incomplete. Record every reading before you submit.'})
    total = sum(p['weight'] for p in parts)
    for p in parts:
        p['share'] = round(p['weight'] / total * 100)
        p['earned'] = round(p['weight'] * p['fraction'] / total * 100)
        p['pct'] = round(p['fraction'] * 100)
        p['state'] = 'good' if p['fraction'] >= 0.999 else 'partial' if p['fraction'] > 0 else 'missed'
    revise = []
    if not exam:
        revise = [{'q': _clean(it.get('q')), 'chosen': _clean(it.get('chosen')), 'correct': _clean(it.get('correct'))}
                  for it in (viva.get('items') or []) if isinstance(it, dict) and not it.get('ok')][:40]
    score = at.auto_score or 0
    headline = 'Strong work' if score >= 85 else 'Good, with gaps to close' if score >= 60 else 'This needs another pass'
    left = max(0, a.max_attempts - a.attempts.filter(student_id=at.student_id).exclude(status=Attempt.STARTED).count()) if at.pk else 0
    notes = []
    if at.timed_out:
        notes.append('Submitted when the time limit ran out.')
    if at.is_late:
        notes.append('Submitted after the due date, so it is marked late.')
    return {'attempt': at.pk, 'headline': headline, 'score': at.auto_score, 'marks': at.final_marks, 'max_marks': float(a.max_marks),
            'parts': parts, 'revise': revise, 'notes': notes, 'attempts_left': left, 'graded': at.status == Attempt.GRADED,
            'provisional': at.manual_marks is None}
