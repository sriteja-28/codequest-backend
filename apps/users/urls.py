from django.urls import path

from .oauth.views import (
    IdentityDisconnectView,
    IdentityListView,
    OAuthCallbackView,
    OAuthStartView,
)
from .views import DevLoginView, LogoutView, MeView, RefreshTokenView

urlpatterns = [
    # Local development only; 404 unless DEV_PASSWORD_AUTH is on.
    path("dev-login/", DevLoginView.as_view(), name="auth-dev-login"),
    path("oauth/<str:provider>/start/", OAuthStartView.as_view(), name="auth-oauth-start"),
    path("oauth/<str:provider>/callback/", OAuthCallbackView.as_view(), name="auth-oauth-callback"),
    path("identities/", IdentityListView.as_view(), name="auth-identities"),
    path("identities/<str:provider>/", IdentityDisconnectView.as_view(), name="auth-identity-disconnect"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
]
