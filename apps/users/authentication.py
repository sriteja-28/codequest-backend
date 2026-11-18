"""
Cookie-based JWT authentication for DRF.
Reads the access token from an HTTP-only cookie instead of Authorization header.
Falls back to the Authorization header for CLI tools.

An invalid/expired token, a deleted or deactivated user, or a banned user is
treated as anonymous (authenticate() returns None). Protected endpoints then
answer 401 (the frontend refreshes the token once), while public endpoints keep
working for visitors who still carry a stale cookie.
"""

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 1. Try cookie first
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"))

        # 2. Fall back to Authorization header (CLI tools)
        if raw_token is None:
            header = self.get_header(request)
            if header is None:
                return None
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
        except (InvalidToken, TokenError, AuthenticationFailed):
            return None

        if getattr(user, "is_banned", False):
            return None

        return user, validated_token
