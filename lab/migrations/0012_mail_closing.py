from django.db import migrations, models


def keep_regards(apps, schema_editor):
    """Every message sent so far ended with a fixed "Regards,": it is now kept on the message itself."""
    apps.get_model('lab', 'MailMessage').objects.filter(direction='out').update(closing='Regards,')


class Migration(migrations.Migration):

    dependencies = [
        ('lab', '0011_mail_formatting'),
    ]

    operations = [
        migrations.AddField(
            model_name='mailmessage',
            name='closing',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.RunPython(keep_regards, migrations.RunPython.noop),
    ]
