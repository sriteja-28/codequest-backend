"""HTTP-only JWT cookie helpers shared by every way of signing in."""

from django.conf import settings
from django.contrib.auth.models import update_last_login
from rest_framework_simplejwt.tokens import RefreshToken


def clear_auth_cookies(response):
    jwt_settings = settings.SIMPLE_JWT
    samesite = jwt_settings.get("AUTH_COOKIE_SAMESITE", "Lax")
    response.delete_cookie(jwt_settings.get("AUTH_COOKIE", "access_token"), samesite=samesite)
    response.delete_cookie(jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token"), samesite=samesite)
    return response


def set_auth_cookies(response, refresh_token):
    """Set the access + refresh JWT cookies on the response."""
    jwt_settings = settings.SIMPLE_JWT
    secure = jwt_settings.get("AUTH_COOKIE_SECURE", False)
    http_only = jwt_settings.get("AUTH_COOKIE_HTTP_ONLY", True)
    samesite = jwt_settings.get("AUTH_COOKIE_SAMESITE", "Lax")
    response.set_cookie(
        key=jwt_settings.get("AUTH_COOKIE", "access_token"),
        value=str(refresh_token.access_token),
        max_age=int(jwt_settings["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        secure=secure,
        httponly=http_only,
        samesite=samesite,
    )
    response.set_cookie(
        key=jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        value=str(refresh_token),
        max_age=int(jwt_settings["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        secure=secure,
        httponly=http_only,
        samesite=samesite,
    )
    return response


def start_session(response, user):
    """
    Sign `user` in on this response: record last_login and set fresh JWT cookies.
    last_active_date (the streak date) is deliberately untouched: it only moves
    when a solution is accepted.
    """
    update_last_login(None, user)
    return set_auth_cookies(response, RefreshToken.for_user(user))
