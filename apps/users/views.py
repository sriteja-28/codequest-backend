from django.conf import settings
from django.contrib.auth import login as django_login
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .backends import staff_session_backend
from .cookies import clear_auth_cookies, set_auth_cookies, start_session
from .models import User
from .progress import get_user_progress
from .serializers import DevLoginSerializer, UserMeSerializer


class DevLoginView(APIView):
    """
    POST /api/auth/dev-login/ — email + password for local development only.

    There is no public password sign-up or sign-in in this product: production
    accounts are Google/GitHub identities. This endpoint exists so a developer
    can test multiple roles on one machine; it answers 404 unless
    settings.DEV_PASSWORD_AUTH is on (development settings only).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        if not getattr(settings, "DEV_PASSWORD_AUTH", False):
            raise Http404
        serializer = DevLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        response = Response(
            {"message": "Signed in (development).", "user": UserMeSerializer(user).data},
            status=status.HTTP_200_OK,
        )
        start_session(response, user)
        if user.is_staff:
            django_login(request, user, backend=staff_session_backend())
        return response


class LogoutView(APIView):
    # AllowAny: logging out must work even when the access token has already
    # expired; it only revokes the refresh token carried by this browser.
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(
            settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
        )
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # expired / already blacklisted — nothing to revoke

        response = Response({"message": "Logged out."}, status=status.HTTP_200_OK)
        return clear_auth_cookies(response)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserMeSerializer(request.user).data)

    def patch(self, request):
        serializer = UserMeSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MyProgressView(APIView):
    """GET /api/users/me/progress/ — cached dashboard aggregate."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_user_progress(request.user))


class RefreshTokenView(APIView):
    """
    POST /api/auth/refresh/ — exchange the refresh cookie for new cookies.

    With ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION (base settings) the
    presented refresh token is blacklisted and a new one is issued, so a stolen
    refresh token stops working after its next legitimate use. The frontend
    serialises refresh calls (one in flight per tab) to avoid racing itself.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(
            settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
        )
        if not raw_refresh:
            return Response({"detail": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        invalid = Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh = RefreshToken(raw_refresh)  # verifies signature, expiry, blacklist
        except TokenError:
            return clear_auth_cookies(invalid)

        user = User.objects.filter(pk=refresh.get(jwt_api_settings.USER_ID_CLAIM)).first()
        if user is None or not user.is_active or user.is_banned:
            return clear_auth_cookies(invalid)

        if jwt_api_settings.ROTATE_REFRESH_TOKENS:
            if jwt_api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except TokenError:
                    return clear_auth_cookies(invalid)
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()

        response = Response({"message": "Token refreshed."}, status=status.HTTP_200_OK)
        return set_auth_cookies(response, refresh)
