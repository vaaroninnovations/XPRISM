from django.core.management.base import BaseCommand

from lab import mailbox


class Command(BaseCommand):
    help = "Bring new mail into the super admins' mailbox (Platform > Mailbox). Run it from cron to receive mail without anyone opening the page."

    def handle(self, *args, **options):
        new, error = mailbox.fetch()
        if error:
            self.stderr.write(error)
        self.stdout.write(f'{new} new message{"s" if new != 1 else ""}')
