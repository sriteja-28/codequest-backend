"""Django authentication backends.

Production uses Django's ModelBackend solely for staff access to the Django
admin; the public site signs in through Google/GitHub OAuth and never accepts
a password. Development can opt into the same password check for seeded local
accounts by installing DevPasswordBackend (development/test settings only).
"""

from django.conf import settings
from django.contrib.auth.backends import ModelBackend


class DevPasswordBackend(ModelBackend):
    """ModelBackend gated on settings.DEV_PASSWORD_AUTH."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not getattr(settings, "DEV_PASSWORD_AUTH", False):
            return None
        return super().authenticate(request, username=username, password=password, **kwargs)


MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"


def staff_session_backend() -> str:
    """The installed backend to record on a Django admin session we create."""
    backends = list(settings.AUTHENTICATION_BACKENDS)
    return MODEL_BACKEND if MODEL_BACKEND in backends else backends[0]
