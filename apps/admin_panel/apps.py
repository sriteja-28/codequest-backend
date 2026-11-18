from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.admin_panel'

    def ready(self):
        # Django admin changes land in the same audit trail as dashboard changes.
        from django.contrib.admin.models import LogEntry
        from django.db.models.signals import post_save

        from .audit import mirror_django_admin

        post_save.connect(mirror_django_admin, sender=LogEntry, dispatch_uid="admin-panel-mirror-logentry")
