"""
Cookie-based JWT authentication for DRF.
Reads the access token from an HTTP-only cookie instead of Authorization header.
Falls back to header for internal API calls (e.g., judge service).
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 1. Try cookie first
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"))

        # 2. Fall back to Authorization header (for judge service, CLI tools)
        if raw_token is None:
            header = self.get_header(request)
            if header is None:
                return None
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            return None

        return self.get_user(validated_token), validated_token