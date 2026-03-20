from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import RegisterSerializer, LoginSerializer, UserMeSerializer


def _set_auth_cookies(response, refresh_token):
    """Set HTTP-only JWT cookies on the response."""
    jwt_settings = settings.SIMPLE_JWT
    secure = jwt_settings.get("AUTH_COOKIE_SECURE", False)
    http_only = jwt_settings.get("AUTH_COOKIE_HTTP_ONLY", True)
    samesite = jwt_settings.get("AUTH_COOKIE_SAMESITE", "Lax")

    access_lifetime = jwt_settings.get("ACCESS_TOKEN_LIFETIME")
    refresh_lifetime = jwt_settings.get("REFRESH_TOKEN_LIFETIME")

    response.set_cookie(
        key=jwt_settings.get("AUTH_COOKIE", "access_token"),
        value=str(refresh_token.access_token),
        max_age=int(access_lifetime.total_seconds()),
        secure=secure,
        httponly=http_only,
        samesite=samesite,
    )
    response.set_cookie(
        key=jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        value=str(refresh_token),
        max_age=int(refresh_lifetime.total_seconds()),
        secure=secure,
        httponly=http_only,
        samesite=samesite,
    )
    return response


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        response = Response(
            {"message": "Registration successful.", "user": UserMeSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )
        return _set_auth_cookies(response, refresh)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Update last active
        user.last_active_date = timezone.now().date()
        user.save(update_fields=["last_active_date"])

        refresh = RefreshToken.for_user(user)
        response = Response(
            {"message": "Login successful.", "user": UserMeSerializer(user).data},
            status=status.HTTP_200_OK,
        )
        return _set_auth_cookies(response, refresh)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            raw_refresh = request.COOKIES.get(
                settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
            )
            if raw_refresh:
                token = RefreshToken(raw_refresh)
                token.blacklist()
        except Exception:
            pass  # Already invalid — that's fine

        response = Response({"message": "Logged out."}, status=status.HTTP_200_OK)
        response.delete_cookie(settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"))
        response.delete_cookie(settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token"))
        return response


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


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(
            settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
        )
        if not raw_refresh:
            return Response({"detail": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(raw_refresh)
            response = Response({"message": "Token refreshed."}, status=status.HTTP_200_OK)
            return _set_auth_cookies(response, refresh)
        except Exception:
            return Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_401_UNAUTHORIZED)