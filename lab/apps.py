from django.apps import AppConfig


class LabConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lab'

    def ready(self):
        from django.contrib.auth.signals import user_logged_out

        def end_trial_visits(sender, request, user, **kw):
            if user is not None:
                from .access import consume_open
                consume_open(user, 'logout')
        user_logged_out.connect(end_trial_visits, dispatch_uid='lab_end_trial_visits')
