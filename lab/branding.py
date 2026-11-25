"""Report branding: the institute's logo, name and department at the top of every printed report.

The header always carries the AltVivo and XPRISM marks on the right. The left side comes from, in order:
the faculty member's own branding (theirs, or the assignment setter's for a student doing an assignment),
then the college's branding, then plain names (the college name, or an individual's institution).
"""
import html

from django import forms
from django.contrib.staticfiles.storage import staticfiles_storage

from .models import ReportBranding, Role

FIELDS = ('institute_name', 'department', 'address_line')


def sniff_image(data):
    """The real type of an uploaded image from its first bytes, or '' when it is not PNG, JPEG or WebP."""
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return ''


def can_brand_self(user):
    """Faculty, lab assistants and college admins may add their own branding, and so may individual (college-less) users."""
    if not user.is_authenticated or user.is_shared_demo:
        return False
    return user.is_platform_admin or user.role in (Role.FACULTY, Role.LAB_ASSISTANT, Role.COLLEGE_ADMIN) or user.college_id is None


def _own(obj):
    try:
        return obj.report_branding
    except ReportBranding.DoesNotExist:
        return None


def resolve(user, setter=None):
    """The branding a report printed by `user` carries. `setter` is the faculty member whose assignment a student is doing."""
    out = {'institute_name': '', 'department': '', 'address_line': '', 'logo': ''}
    college = user.college if user.is_authenticated else None
    layers = []
    if college:
        out['institute_name'] = college.name
        layers.append(_own(college))
    elif user.is_authenticated:
        out['institute_name'] = user.institution
    if not user.is_authenticated:
        person = None
    elif user.role == Role.STUDENT and college:     # college students carry their college's branding, or their setter's
        person = setter if setter and setter.college_id == user.college_id else None
    else:
        person = user
    if person:
        layers.append(_own(person))
    for b in layers:
        if not b:
            continue
        for f in FIELDS:
            v = getattr(b, f).strip()
            if v and not (f == 'institute_name' and college and b.user_id):   # inside a college the institute name is the college's
                out[f] = v
        if b.logo_data_uri:
            out['logo'] = b.logo_data_uri
    return out


HEADER_CSS = '''<style>
.xr-brand{display:flex;align-items:center;gap:14px;padding:10px 4px 12px;border-bottom:2px solid #1e293b;margin-bottom:4px}
.xr-brand-logo{height:60px;width:auto;max-width:150px;object-fit:contain;flex:none}
.xr-brand-mid{flex:1;min-width:0}
.xr-brand-inst{font-size:17px;font-weight:800;color:#0f172a;line-height:1.2;letter-spacing:.01em}
.xr-brand-dept{font-size:12.5px;font-weight:600;color:#334155;margin-top:2px}
.xr-brand-addr{font-size:11px;color:#64748b;margin-top:1px}
.xr-brand-by{display:flex;align-items:center;gap:10px;flex:none;border-left:1px solid #cbd5e1;padding-left:12px}
.xr-brand-by img{height:30px;width:auto}
.xr-brand-by span{display:block;font-size:8.5px;text-transform:uppercase;letter-spacing:.08em;color:#94a3b8;text-align:right;margin-bottom:2px}
@media (max-width:640px){.xr-brand{flex-wrap:wrap}.xr-brand-by{border-left:0;padding-left:0}}
@media print{.xr-brand{-webkit-print-color-adjust:exact;print-color-adjust:exact;break-inside:avoid}}
</style>'''


def header_html(b):
    """The branding strip placed at the top of the report (the observation sheet), on screen and in print."""
    logo = f'<img class="xr-brand-logo" src="{b["logo"]}" alt="Institute logo">' if b['logo'] else ''
    lines = [f'<div class="xr-brand-inst">{html.escape(b["institute_name"])}</div>' if b['institute_name'] else '',
             f'<div class="xr-brand-dept">{html.escape(b["department"])}</div>' if b['department'] else '',
             f'<div class="xr-brand-addr">{html.escape(b["address_line"])}</div>' if b['address_line'] else '']
    av, xp = staticfiles_storage.url('img/altvivo-wordmark.png'), staticfiles_storage.url('img/xprism-lockup.png')
    return (f'{HEADER_CSS}<div class="xr-brand" id="reportBranding">{logo}<div class="xr-brand-mid">{"".join(lines)}</div>'
            f'<div class="xr-brand-by"><div><span>Powered by</span><div style="display:flex;gap:10px;align-items:center">'
            f'<img src="{xp}" alt="XPRISM"><img src="{av}" alt="AltVivo"></div></div></div></div>')


class ReportBrandingForm(forms.ModelForm):
    logo_file = forms.FileField(label='Logo', required=False, help_text='PNG, JPEG or WebP, up to 300 KB. A transparent PNG looks best.')
    remove_logo = forms.BooleanField(label='Remove the current logo', required=False)

    class Meta:
        model = ReportBranding
        fields = ['institute_name', 'department', 'address_line']

    def __init__(self, *a, show_institute=True, **kw):
        super().__init__(*a, **kw)
        if not show_institute:
            del self.fields['institute_name']
        self.fields['department'].help_text = 'e.g. "Department of Pharmacology"'
        self.fields['address_line'].help_text = 'Optional: address, university affiliation or accreditation.'
        from .forms import CHECK, INPUT
        for name, f in self.fields.items():
            f.widget.attrs.setdefault('class', CHECK if name == 'remove_logo' else INPUT)
        self.fields['logo_file'].widget.attrs['accept'] = 'image/png,image/jpeg,image/webp'

    def clean_logo_file(self):
        f = self.cleaned_data.get('logo_file')
        if not f:
            return None
        if f.size > ReportBranding.MAX_LOGO_BYTES:
            raise forms.ValidationError('The logo is larger than 300 KB. Please resize it and try again.')
        data = f.read()
        kind = sniff_image(data)
        if not kind:
            raise forms.ValidationError('Upload a PNG, JPEG or WebP image.')
        return kind, data

    def save(self, commit=True):
        b = super().save(commit=False)
        logo = self.cleaned_data.get('logo_file')
        if logo:
            b.logo_type, b.logo = logo
        elif self.cleaned_data.get('remove_logo'):
            b.logo_type, b.logo = '', None
        if commit:
            b.save()
        return b
