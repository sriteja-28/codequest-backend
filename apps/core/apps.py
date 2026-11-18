from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Cross-cutting platform endpoints: health checks and public runtime config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"

    def ready(self):
        # Connects the cache-invalidation signals for site config.
        from . import site  # noqa: F401
