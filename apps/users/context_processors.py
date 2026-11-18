"""Template context for the Django admin sign-in page.

The admin login override offers Google/GitHub when this deployment has real
credentials. The normal staff username/password form stays available.
"""

from django.conf import settings


def admin_login(request):
    from apps.users.oauth.providers import configured_providers

    return {
        "oauth_providers": [p for p in configured_providers() if p["enabled"]],
        "dev_password_auth": bool(getattr(settings, "DEV_PASSWORD_AUTH", False)),
    }
