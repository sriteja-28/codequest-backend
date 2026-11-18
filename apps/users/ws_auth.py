"""
WebSocket authentication for Channels using the REST API's HTTP-only JWT cookie.

The browser sends cookies on the WebSocket handshake, so the same
`access_token` cookie that authenticates REST calls authenticates sockets.
Invalid, expired, banned or inactive users become AnonymousUser; consumers
decide whether anonymous access is allowed.
"""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http.cookie import parse_cookie


@database_sync_to_async
def _user_from_access_token(raw_token: str):
    from rest_framework.exceptions import AuthenticationFailed
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

    auth = JWTAuthentication()
    try:
        validated = auth.get_validated_token(raw_token)
        user = auth.get_user(validated)
    except (InvalidToken, TokenError, AuthenticationFailed):
        return AnonymousUser()
    if not user.is_active or getattr(user, "is_banned", False):
        return AnonymousUser()
    return user


def _access_token_from_scope(scope) -> str | None:
    cookie_name = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            return parse_cookie(value.decode("latin1")).get(cookie_name) or None
    return None


class JWTCookieAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        raw_token = _access_token_from_scope(scope)
        scope["user"] = await _user_from_access_token(raw_token) if raw_token else AnonymousUser()
        return await super().__call__(scope, receive, send)
