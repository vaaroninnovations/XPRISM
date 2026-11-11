from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

STATE = {
    'open': ('Open', 'bg-sky-50 text-sky-800 border-sky-200'),
    'in_progress': ('In progress', 'bg-amber-50 text-amber-800 border-amber-200'),
    'overdue': ('Overdue', 'bg-rose-50 text-rose-800 border-rose-200'),
    'upcoming': ('Upcoming', 'bg-slate-50 text-slate-600 border-slate-200'),
    'submitted': ('Submitted', 'bg-indigo-50 text-indigo-800 border-indigo-200'),
    'graded': ('Graded', 'bg-emerald-50 text-emerald-800 border-emerald-200'),
    'started': ('In progress', 'bg-amber-50 text-amber-800 border-amber-200'),
}


class CaptureNode(template.Node):
    def __init__(self, nodelist, name):
        self.nodelist, self.name = nodelist, name      # "nodelist" is where Django looks for the blocks inside

    def render(self, context):
        context[self.name] = mark_safe(self.nodelist.render(context).strip())
        return ''


@register.tag
def capture(parser, token):
    """{% capture name %}...{% endcapture %}: keeps what a block rendered so the page can print it more than once."""
    name = token.split_contents()[1]
    nodelist = parser.parse(('endcapture',))
    parser.delete_first_token()
    return CaptureNode(nodelist, name)


@register.filter
def state_badge(state):
    label, cls = STATE.get(state, (state, 'bg-slate-50 text-slate-600 border-slate-200'))
    return format_html('<span class="text-[11px] font-semibold border px-2 py-0.5 rounded-full {}">{}</span>', cls, label)


@register.filter
def marks(at):
    if not at or at.final_marks is None:
        return '—'
    v = at.final_marks
    return f'{v:g}'


@register.filter
def get(d, k):
    try:
        return d.get(k)
    except AttributeError:
        return None


@register.filter
def pct(v, total):
    try:
        return round(float(v) / float(total) * 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def paragraphs(text):
    """Text split where the writer left an empty line, for templates that wrap each paragraph themselves."""
    import re
    return [p for p in re.split(r'\n\s*\n', str(text or '').replace('\r\n', '\n').strip('\n')) if p.strip()]
