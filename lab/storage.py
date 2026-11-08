import os

from django.contrib.staticfiles.storage import StaticFilesStorage


class VersionedStaticFilesStorage(StaticFilesStorage):
    """Adds ?v=<modified time> to asset URLs.

    nginx tells browsers to keep /assets/ for 30 days, so a changed file needs a
    new URL or returning visitors keep the old copy after a deployment.
    """

    def url(self, name):
        url = super().url(name)
        try:
            return f'{url}?v={int(os.path.getmtime(self.path(name)))}'
        except OSError:  # not collected yet, for example under runserver
            return url
