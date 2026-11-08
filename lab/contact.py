"""What people can write to us about. Each subject has its own sub-topics; the contact form and the super admin inbox both use this list."""

TOPICS = [
    ('demo', 'Demo request', [
        ('online', 'Live online demo'),
        ('campus', 'On-campus demo'),
        ('faculty_login', 'Demo login for faculty'),
        ('module', 'Walkthrough of specific modules'),
    ]),
    ('quotation', 'Quotation request', [
        ('college', 'College subscription'),
        ('university', 'University or multi-campus subscription'),
        ('individual', 'Individual subscription'),
        ('renewal', 'Renewal of a subscription'),
        ('custom', 'Custom modules or features'),
    ]),
    ('technical', 'Technical problem', [
        ('sign_in', 'Cannot sign in or reset my password'),
        ('module', 'A module does not load or stops working'),
        ('saving', 'Results, submissions or marks are not saving'),
        ('exam', 'Exam mode or timer problem'),
        ('display', 'Display, browser or mobile problem'),
        ('other', 'Another technical problem'),
    ]),
    ('account', 'Account and access', [
        ('details', 'Change my name or e-mail'),
        ('class_code', 'Class code or joining a batch'),
        ('college_admin', 'College admin or staff accounts'),
        ('deactivate', 'Deactivate or restore an account'),
    ]),
    ('billing', 'Billing and payments', [
        ('invoice', 'Invoice or receipt'),
        ('status', 'Payment status'),
        ('tax', 'GST or tax details'),
        ('refund', 'Refund request'),
    ]),
    ('free_month', 'Free one-month access', [
        ('eligibility', 'Eligibility'),
        ('status', 'Status of my application'),
        ('after', 'Continuing after the free month'),
    ]),
    ('content', 'Academic content', [
        ('error', 'Report an error in a module'),
        ('new_module', 'Suggest a new module'),
        ('syllabus', 'PCI syllabus mapping'),
        ('viva', 'Viva questions or marking'),
    ]),
    ('training', 'Training and onboarding', [
        ('faculty', 'Faculty training'),
        ('students', 'Student orientation'),
        ('setup', 'Setting up batches and assignments'),
        ('docs', 'Help with the documentation'),
    ]),
    ('partnership', 'Partnership and research', [
        ('institution', 'Institutional partnership'),
        ('research', 'Research collaboration'),
        ('workshop', 'Conference or workshop'),
        ('reseller', 'Reseller or distributor'),
    ]),
    ('privacy', 'Privacy and data', [
        ('download', 'Download my data'),
        ('correct', 'Correct my data'),
        ('delete', 'Delete my data'),
        ('grievance', 'Raise a grievance'),
    ]),
    ('general', 'General enquiry', [
        ('question', 'General question'),
        ('feedback', 'Feedback'),
        ('media', 'Media or press'),
        ('other', 'Something else'),
    ]),
]

TOPIC_CHOICES = [(key, label) for key, label, _ in TOPICS]
SUBTOPICS = {key: dict(subs) for key, _, subs in TOPICS}
# one value per sub-topic in the form, so a form without JavaScript still works: "topic.subtopic"
GROUPED_SUBTOPICS = [(label, [(f'{key}.{sub}', sub_label) for sub, sub_label in subs]) for key, label, subs in TOPICS]
# a demo or a quotation is for an institution, so we need to know which one
NEEDS_INSTITUTION = {'demo', 'quotation', 'partnership', 'training'}


def subtopic_label(topic, subtopic):
    return SUBTOPICS.get(topic, {}).get(subtopic, subtopic)
