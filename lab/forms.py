import re
import secrets

from django import forms
from django.contrib.auth import password_validation
from django.utils import timezone

from .contact import GROUPED_SUBTOPICS, NEEDS_INSTITUTION, SUBTOPICS
from .models import Assignment, Batch, College, ContactRequest, Experiment, FreeYearApplication, Role, User

INPUT = 'w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500'
CHECK = 'accent-teal-600 w-4 h-4'


class StyledMixin:
    def _style(self):
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault('class', CHECK)
            elif isinstance(w, forms.CheckboxSelectMultiple):
                w.attrs.setdefault('class', CHECK)
            else:
                w.attrs.setdefault('class', INPUT)


def temp_password():
    alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(10))


def make_username(college, roll_or_name):
    base = re.sub(r'[^a-z0-9]+', '', str(roll_or_name).lower())[:30] or 'user'
    return f'{college.code}-{base}' if college else base


class SignupForm(StyledMixin, forms.Form):
    class_code = forms.CharField(max_length=12, help_text='Given to you by your faculty')
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60, required=False)
    roll_no = forms.CharField(label='Roll / enrolment no.', max_length=40)
    email = forms.EmailField(required=False, help_text='Optional; used only for password reset')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)
    accept = forms.BooleanField(label='I have read and accept the Privacy Policy, Terms of Service and Conditions of Use')
    age_ok = forms.BooleanField(label='I am 18 years or older, or my parent/guardian has consented to my use of this service')

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean_class_code(self):
        code = self.cleaned_data['class_code'].strip().upper()
        try:
            self.batch = Batch.objects.select_related('college').get(class_code=code, join_enabled=True, archived=False, college__is_active=True)
        except Batch.DoesNotExist:
            raise forms.ValidationError('This class code is not valid or joining is closed. Check with your faculty.')
        return code

    def clean(self):
        cd = super().clean()
        if cd.get('password1') and cd.get('password1') != cd.get('password2'):
            self.add_error('password2', 'Passwords do not match.')
        if hasattr(self, 'batch') and cd.get('roll_no'):
            self.username = make_username(self.batch.college, cd['roll_no'])
            if User.objects.filter(username=self.username).exists():
                self.add_error('roll_no', 'An account with this roll number already exists in your college. Sign in instead, or ask your faculty to reset your password.')
            elif cd.get('password1'):
                tmp = User(username=self.username, first_name=cd.get('first_name', ''), last_name=cd.get('last_name', ''), email=cd.get('email', ''))
                try:
                    password_validation.validate_password(cd['password1'], tmp)
                except forms.ValidationError as e:
                    self.add_error('password1', e)
        return cd


class ConsentForm(forms.Form):
    accept = forms.BooleanField(label='I have read and accept the Privacy Policy, Terms of Service and Conditions of Use', widget=forms.CheckboxInput(attrs={'class': CHECK}))
    age_ok = forms.BooleanField(label='I am 18 years or older, or my parent/guardian has consented to my use of this service', widget=forms.CheckboxInput(attrs={'class': CHECK}))


class BatchForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['name', 'academic_year', 'join_enabled', 'faculty']
        widgets = {'faculty': forms.CheckboxSelectMultiple}
        labels = {'faculty': 'Faculty for this batch'}

    def __init__(self, *a, college=None, **kw):
        super().__init__(*a, **kw)
        self.fields['faculty'].queryset = User.objects.filter(college=college, role=Role.FACULTY, is_active=True).order_by('first_name')
        self.fields['faculty'].required = False
        self._style()


class DTInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def format_value(self, value):
        if isinstance(value, str) or value is None:
            return value
        if timezone.is_naive(value):
            return value.strftime('%Y-%m-%dT%H:%M')
        return timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')


class AssignmentForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['experiment', 'instructions', 'opens_at', 'due_at', 'max_marks', 'max_attempts', 'allow_late', 'exam_mode', 'time_limit_min']
        widgets = {'opens_at': DTInput, 'due_at': DTInput, 'instructions': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *a, college=None, **kw):
        super().__init__(*a, **kw)
        qs = Experiment.objects.filter(is_active=True)
        if college:
            qs = qs.exclude(pk__in=college.disabled_experiments.values('pk'))
        self.fields['experiment'].queryset = qs
        for f in ('opens_at', 'due_at'):
            self.fields[f].input_formats = ['%Y-%m-%dT%H:%M']
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault('due_at', timezone.now() + timezone.timedelta(days=7))
        self._style()

    def clean(self):
        cd = super().clean()
        if cd.get('opens_at') and cd.get('due_at') and cd['due_at'] <= cd['opens_at']:
            self.add_error('due_at', 'Due date must be after the opening time.')
        if cd.get('exam_mode') and not cd.get('time_limit_min'):
            self.add_error('time_limit_min', 'Set a time limit for exam mode.')
        if cd.get('max_marks') is not None and cd['max_marks'] <= 0:
            self.add_error('max_marks', 'Must be positive.')
        return cd


class StudentAddForm(StyledMixin, forms.Form):
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60, required=False)
    roll_no = forms.CharField(max_length=40)
    email = forms.EmailField(required=False)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class UploadForm(StyledMixin, forms.Form):
    file = forms.FileField(help_text='CSV or Excel (.xlsx) with columns: roll_no, first_name, last_name, email')

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean_file(self):
        f = self.cleaned_data['file']
        if f.size > 2 * 1024 * 1024:
            raise forms.ValidationError('File too large (max 2 MB).')
        if not f.name.lower().endswith(('.csv', '.xlsx')):
            raise forms.ValidationError('Upload a .csv or .xlsx file.')
        return f


class GradeForm(StyledMixin, forms.Form):
    manual_marks = forms.DecimalField(label='Marks (leave blank to use the automatic score)', required=False, min_value=0, decimal_places=1, max_digits=5)
    feedback = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)

    def __init__(self, *a, max_marks=None, **kw):
        super().__init__(*a, **kw)
        self.max_marks = max_marks
        self._style()

    def clean_manual_marks(self):
        v = self.cleaned_data.get('manual_marks')
        if v is not None and self.max_marks is not None and v > self.max_marks:
            raise forms.ValidationError(f'Cannot exceed {self.max_marks}.')
        return v


class StaffUserForm(StyledMixin, forms.Form):
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60, required=False)
    email = forms.EmailField(required=False)
    username = forms.CharField(max_length=60, required=False, help_text='Leave blank to generate from the name')
    role = forms.ChoiceField(choices=[(Role.FACULTY, 'Faculty'), (Role.LAB_ASSISTANT, 'Lab Assistant'), (Role.COLLEGE_ADMIN, 'College Admin')])

    def __init__(self, *a, college=None, **kw):
        super().__init__(*a, **kw)
        self.college = college
        self._style()

    def clean(self):
        cd = super().clean()
        base = cd.get('username') or f"{cd.get('first_name', '')}{cd.get('last_name', '')}"
        self.username = make_username(self.college, base)
        if User.objects.filter(username=self.username).exists():
            self.add_error('username', f'Username "{self.username}" is taken; enter a different one.')
        return cd


class CollegeForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = College
        fields = ['name', 'code', 'location_text', 'contact_email', 'grievance_officer', 'grievance_email', 'is_active', 'subscription_active', 'subscription_until']
        widgets = {'subscription_until': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class CollegeCreateForm(CollegeForm):
    admin_first_name = forms.CharField(label='College admin: first name', max_length=60)
    admin_last_name = forms.CharField(label='College admin: last name', max_length=60, required=False)
    admin_email = forms.EmailField(label='College admin: e-mail', required=False)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class BrandingForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = College
        fields = ['name', 'location_text', 'contact_email', 'grievance_officer', 'grievance_email']

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class DataRequestForm(StyledMixin, forms.Form):
    kind = forms.ChoiceField(choices=[('deletion', 'Delete my account and personal data'), ('correction', 'Correct my personal data')])
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, help_text='For corrections, tell us what should change.')

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class TrialSignupForm(StyledMixin, forms.Form):
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60, required=False)
    email = forms.EmailField(help_text='This is your username. Used only for sign-in and password reset.')
    institution = forms.CharField(label='College / institution', max_length=200, required=False)
    occupation = forms.ChoiceField(label='I am a', choices=[('student', 'Student'), ('faculty', 'Faculty / teacher'), ('researcher', 'Researcher'), ('other', 'Other')])
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)
    accept = forms.BooleanField(label='I have read and accept the Privacy Policy, Terms of Service and Conditions of Use')
    age_ok = forms.BooleanField(label='I am 18 years or older, or my parent/guardian has consented to my use of this service')

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean_email(self):
        e = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=e).exists() or User.objects.filter(email__iexact=e, is_trial_account=True).exists():
            raise forms.ValidationError('An account with this e-mail already exists. Sign in instead.')
        return e

    def clean(self):
        cd = super().clean()
        if cd.get('password1') and cd.get('password1') != cd.get('password2'):
            self.add_error('password2', 'Passwords do not match.')
        elif cd.get('password1') and cd.get('email'):
            tmp = User(username=cd['email'], email=cd['email'], first_name=cd.get('first_name', ''), last_name=cd.get('last_name', ''))
            try:
                password_validation.validate_password(cd['password1'], tmp)
            except forms.ValidationError as e:
                self.add_error('password1', e)
        return cd


class FreeYearApplicationForm(forms.ModelForm):
    """Submitted from the pop-up in templates/lab/_free_year_modal.html, which holds the markup."""
    consent = forms.BooleanField(error_messages={'required': 'Please agree so that we can review your application.'})
    website = forms.CharField(required=False)   # hidden from people: anything here came from a bot

    class Meta:
        model = FreeYearApplication
        fields = ['kind', 'name', 'email', 'phone', 'institution', 'occupation', 'message']

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if phone and not re.fullmatch(r'\+?[0-9][0-9 ()-]{6,18}', phone):
            raise forms.ValidationError('Enter a valid phone number.')
        return phone


class MailComposeForm(StyledMixin, forms.Form):
    """A message written in the super admins' mailbox. The text goes into the XPRISM e-mail template."""
    to = forms.CharField(label='To', max_length=1200, help_text='One e-mail address, or several separated by commas. Everyone listed sees the other addresses.')
    subject = forms.CharField(label='Subject', max_length=255)
    greeting = forms.CharField(label='Greeting name', max_length=120, required=False, help_text='Shown as "Hello Asha,". Leave empty for a plain "Hello,".')
    body = forms.CharField(label='Message', max_length=20000, widget=forms.Textarea(attrs={'rows': 12}), strip=False)
    signoff = forms.CharField(label='Sign-off', max_length=120, required=False, help_text='The line under "Regards,".')

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean_to(self):
        from .free_year import parse_addresses
        from .mailbox import MAX_RECIPIENTS
        valid, invalid = parse_addresses(self.cleaned_data['to'])
        if invalid:
            raise forms.ValidationError(f'Not a valid e-mail address: {", ".join(invalid[:5])}')
        if not valid:
            raise forms.ValidationError('Enter at least one e-mail address.')
        if len(valid) > MAX_RECIPIENTS:
            raise forms.ValidationError(f'At most {MAX_RECIPIENTS} addresses in one message.')
        return valid

    def clean_subject(self):
        subject = ' '.join(self.cleaned_data['subject'].split())        # a line break here would let text into the e-mail headers
        if not subject:
            raise forms.ValidationError('Enter a subject.')
        return subject

    def clean_body(self):
        body = self.cleaned_data['body'].replace('\r\n', '\n').strip('\n')
        if not body.strip():
            raise forms.ValidationError('Write a message.')
        return body

    def clean_greeting(self):
        return ' '.join(self.cleaned_data['greeting'].split())

    def clean_signoff(self):
        return ' '.join(self.cleaned_data['signoff'].split())


class ContactForm(StyledMixin, forms.ModelForm):
    subtopic = forms.ChoiceField(label='Sub-topic', choices=[('', 'Choose a sub-topic')] + GROUPED_SUBTOPICS)
    consent = forms.BooleanField(label='I agree that XPRISM may use these details to respond to this request', error_messages={'required': 'Please agree so that we can respond to you.'})
    website = forms.CharField(required=False, widget=forms.HiddenInput)     # filled only by bots; the visible trap is in the template

    class Meta:
        model = ContactRequest
        fields = ['topic', 'subtopic', 'name', 'email', 'phone', 'institution', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        del self.fields['website']
        self.fields['topic'].choices = [('', 'Choose a subject')] + [c for c in self.fields['topic'].choices if c[0]]
        self.fields['institution'].help_text = 'Needed for demos, quotations, training and partnerships'
        self._style()

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if phone and not re.fullmatch(r'\+?[0-9][0-9 ()-]{6,18}', phone):
            raise forms.ValidationError('Enter a valid phone number.')
        return phone

    def clean(self):
        cd = super().clean()
        topic, _, sub = (cd.get('subtopic') or '').partition('.')
        if cd.get('topic') and cd.get('subtopic'):
            if topic != cd['topic'] or sub not in SUBTOPICS.get(topic, {}):
                self.add_error('subtopic', 'Choose a sub-topic that belongs to this subject.')
            else:
                cd['subtopic'] = sub
        if cd.get('topic') in NEEDS_INSTITUTION and not cd.get('institution', '').strip():
            self.add_error('institution', 'Please tell us your college or institution.')
        return cd


class EthicsAgreementForm(forms.Form):
    agree_ethics = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': CHECK}))
    agree_trial = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': CHECK}))

    def __init__(self, *a, trial=False, **kw):
        super().__init__(*a, **kw)
        self.fields['agree_trial'].required = trial
