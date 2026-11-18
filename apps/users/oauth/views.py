"""
OAuth sign-in endpoints.

    GET  /api/auth/oauth/<provider>/start/          -> {authorization_url}
         (?redirect=1 or Accept: text/html -> 302; used by the Django admin login page)
    POST /api/auth/oauth/<provider>/callback/       {code, state} -> user + cookies
    GET  /api/auth/identities/                      linked sign-in methods
    DELETE /api/auth/identities/<provider>/         disconnect one

The frontend callback page receives the provider redirect, then POSTs the code
and state here. The state cookie binds the response to the browser that started
the flow; a cache marker makes each state token one-time.
"""

import hashlib
import hmac
import logging

from django.conf import settings
from django.contrib.auth import login as django_login
from django.core.cache import cache
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ..backends import staff_session_backend
from ..cookies import start_session
from ..serializers import SocialIdentitySerializer, UserMeSerializer
from . import flow
from .accounts import (
    AccountError,
    connect_identity,
    disconnect_identity,
    sign_in_with_profile,
)
from .http import ProviderError
from .providers import PROVIDERS, ProviderNotConfigured, callback_url, get_provider

logger = logging.getLogger(__name__)

MAX_AUTH_CODE_LENGTH = 4096


def _error(exc: Exception) -> Response:
    if isinstance(exc, (flow.StateError,)):
        return Response(
            {"detail": str(exc), "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, ProviderNotConfigured):
        return Response(
            {"detail": "This sign-in method is not configured on this server.", "code": exc.code},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(exc, ProviderError):
        code = exc.code
        http_status = status.HTTP_404_NOT_FOUND if code == "unknown_provider" else status.HTTP_502_BAD_GATEWAY
        return Response(
            {"detail": "The sign-in provider could not complete the request. Please try again.", "code": code},
            status=http_status,
        )
    if isinstance(exc, AccountError):
        http_status = {
            "not_connected": status.HTTP_404_NOT_FOUND,
            "authentication_required": status.HTTP_401_UNAUTHORIZED,
            "email_taken": status.HTTP_409_CONFLICT,
            "identity_conflict": status.HTTP_409_CONFLICT,
            "provider_already_connected": status.HTTP_409_CONFLICT,
            "last_credential": status.HTTP_409_CONFLICT,
            "sign_in_conflict": status.HTTP_409_CONFLICT,
        }.get(exc.code, status.HTTP_403_FORBIDDEN)
        return Response({"detail": exc.detail, "code": exc.code}, status=http_status)
    raise exc


def _with_cleared_state(response: Response, provider_id: str) -> Response:
    return flow.clear_state_cookie(response, provider_id)


def _consume_state(provider_id: str, state: str) -> None:
    """Reject a state token that already completed a callback."""
    digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
    key = f"oauth:used-state:{provider_id}:{digest}"
    try:
        if not cache.add(key, 1, timeout=settings.OAUTH_STATE_MAX_AGE):
            raise flow.StateError("state_reused", "This sign-in attempt was already used. Please try again.")
    except flow.StateError:
        raise
    except Exception:  # cache outage: the signed cookie still protects the flow
        logger.warning("oauth state replay cache unavailable", exc_info=True)


def _wants_redirect(request) -> bool:
    if request.query_params.get("redirect") in ("1", "true", "yes"):
        return True
    return "text/html" in (request.headers.get("Accept") or "")


class OAuthStartView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth"

    def get(self, request, provider):
        if provider not in PROVIDERS:
            return _error(ProviderError("unknown_provider", "unknown provider"))

        intent = request.query_params.get("intent", "login")
        if intent not in ("login", "connect"):
            return Response(
                {"detail": "Unknown sign-in intent.", "code": "bad_intent"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if intent == "connect" and not request.user.is_authenticated:
            return Response(
                {"detail": "Sign in before connecting another sign-in method.", "code": "authentication_required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            oauth_provider = get_provider(provider)
        except ProviderError as exc:
            return _error(exc)

        redirect_uri = callback_url(provider)
        state = flow.new_flow_state(
            redirect_uri=redirect_uri,
            next_url=flow.safe_next(request.query_params.get("next")),
            intent=intent,
            user_id=request.user.pk if intent == "connect" else None,
        )
        authorization_url = oauth_provider.authorization_url(
            redirect_uri=redirect_uri,
            state=state.state,
            nonce=state.nonce,
            code_challenge=flow.challenge_for(state),
        )
        if _wants_redirect(request):
            response = HttpResponseRedirect(authorization_url)
        else:
            response = Response({"authorization_url": authorization_url})
        return flow.set_state_cookie(response, provider, state)


class OAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth"

    def post(self, request, provider):
        if provider not in PROVIDERS:
            return _error(ProviderError("unknown_provider", "unknown provider"))

        raw_state = request.COOKIES.get(flow.cookie_name(provider))
        if not raw_state:
            return _error(flow.StateError("state_missing", "Start the sign-in again from this browser."))
        try:
            state = flow.decode(raw_state)
        except flow.StateError as exc:
            return _error(exc)

        state_param = str(request.data.get("state") or "")
        if not hmac.compare_digest(state.state, state_param):
            return _with_cleared_state(
                _error(flow.StateError("state_mismatch", "The sign-in response did not match this attempt.")),
                provider,
            )

        code = str(request.data.get("code") or "")
        if not code or len(code) > MAX_AUTH_CODE_LENGTH:
            return _with_cleared_state(
                _error(flow.StateError("code_missing", "The sign-in provider returned no authorization code.")),
                provider,
            )

        try:
            _consume_state(provider, state.state)
        except flow.StateError as exc:
            return _with_cleared_state(_error(exc), provider)

        try:
            oauth_provider = get_provider(provider)
            profile = oauth_provider.exchange_code(
                code=code,
                redirect_uri=state.redirect_uri,
                code_verifier=state.code_verifier,
                nonce=state.nonce,
            )
            if state.intent == "connect":
                return self._connect(request, provider, state, profile)
            return self._sign_in(request, provider, state, profile)
        except (ProviderError, AccountError) as exc:
            logger.info("oauth callback failed provider=%s code=%s", provider, getattr(exc, "code", "error"))
            return _with_cleared_state(_error(exc), provider)

    def _sign_in(self, request, provider, state: flow.FlowState, profile) -> Response:
        result = sign_in_with_profile(provider, profile)
        user = result.user
        if not user.is_active or user.is_banned:
            raise AccountError("account_disabled", "This account is deactivated or suspended.")

        response = Response({
            "message": "Signed in.",
            "user": UserMeSerializer(user).data,
            "next": state.next_url,
            "created": result.created,
            "linked_legacy": result.linked_legacy,
        })
        start_session(response, user)
        # Staff can go straight to the Django admin after signing in there.
        if user.is_staff:
            django_login(request, user, backend=staff_session_backend())
        return _with_cleared_state(response, provider)

    def _connect(self, request, provider, state: flow.FlowState, profile) -> Response:
        if not request.user.is_authenticated or request.user.pk != state.user_id:
            raise AccountError(
                "authentication_required",
                "Sign in as the same user before connecting a sign-in method.",
            )
        identity, created = connect_identity(request.user, provider, profile)
        response = Response({
            "message": f"{identity.get_provider_display()} connected." if created
            else f"{identity.get_provider_display()} was already connected.",
            "identity": SocialIdentitySerializer(identity).data,
            "next": state.next_url,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        return _with_cleared_state(response, provider)


class IdentityListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(SocialIdentitySerializer(request.user.identities.all(), many=True).data)


class IdentityDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, provider):
        try:
            disconnect_identity(request.user, provider)
        except AccountError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
