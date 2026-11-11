from django.db import migrations, models


def whole_greeting(apps, schema_editor):
    """The greeting used to hold only the name after a fixed "Hello". It now holds the whole line, so the
    messages already sent keep reading as they were sent."""
    MailMessage = apps.get_model('lab', 'MailMessage')
    for m in MailMessage.objects.filter(direction='out'):
        m.greeting = (f'Hello {m.greeting},' if m.greeting else 'Hello,')[:120]
        m.save(update_fields=['greeting'])


class Migration(migrations.Migration):

    dependencies = [
        ('lab', '0010_mailbox'),
    ]

    operations = [
        migrations.AddField(
            model_name='mailmessage',
            name='body_html',
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(whole_greeting, migrations.RunPython.noop),
    ]
