"""
OAuth flow state: state token, nonce, PKCE verifier and safe redirect target.

The whole flow state travels in a short-lived signed, HTTP-only cookie scoped
to /api/auth/oauth/. Nothing secret is stored server-side; the cookie is signed
with SECRET_KEY, so the browser cannot tamper with the redirect target, the
nonce or the PKCE verifier. The authorization code itself is one-time at the
provider, and a cache marker additionally makes each state token one-time
(see oauth/views.py).

Cookie rules mirror the JWT cookies: HttpOnly, Lax (the provider redirects
back with a top-level GET), Secure in production, short max age.
"""

import base64
import hashlib
import secrets
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing

STATE_SALT = "codequest.oauth.flow-state"
COOKIE_PREFIX = "oauth_state_"
CODE_VERIFIER_BYTES = 64
MAX_NEXT_LENGTH = 500


class StateError(Exception):
    """The state cookie is missing, expired, tampered with, or malformed."""

    def __init__(self, code: str = "state_invalid", detail: str = ""):
        super().__init__(detail or code)
        self.code = code


@dataclass(frozen=True)
class FlowState:
    state: str
    nonce: str
    code_verifier: str
    redirect_uri: str
    next_url: str = "/"
    intent: str = "login"       # "login" | "connect"
    user_id: int | None = None


def safe_next(raw: str | None, fallback: str = "/") -> str:
    """Only allow same-site absolute paths (?next=/problems/two-sum)."""
    if not raw or len(raw) > MAX_NEXT_LENGTH:
        return fallback
    if not raw.startswith("/") or raw.startswith("//") or "\\" in raw:
        return fallback
    if any(ch in raw for ch in ("\r", "\n", "\0")):
        return fallback
    # Never bounce back into the auth pages themselves.
    if urlsplit(raw).path.startswith("/auth/"):
        return fallback
    return raw


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_flow_state(
    *,
    redirect_uri: str,
    next_url: str = "/",
    intent: str = "login",
    user_id: int | None = None,
) -> FlowState:
    if intent not in ("login", "connect"):
        raise ValueError("intent must be 'login' or 'connect'")
    verifier = secrets.token_urlsafe(CODE_VERIFIER_BYTES)
    return FlowState(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        code_verifier=verifier,
        redirect_uri=redirect_uri,
        next_url=safe_next(next_url),
        intent=intent,
        user_id=user_id,
    )


def challenge_for(flow: FlowState) -> str:
    return code_challenge(flow.code_verifier)


def encode(flow: FlowState) -> str:
    return signing.dumps(asdict(flow), salt=STATE_SALT, compress=True)


def decode(raw: str, *, max_age: int | None = None) -> FlowState:
    try:
        payload = signing.loads(
            raw,
            salt=STATE_SALT,
            max_age=max_age if max_age is not None else settings.OAUTH_STATE_MAX_AGE,
        )
    except signing.SignatureExpired:
        raise StateError("state_expired", "The sign-in attempt expired. Please try again.") from None
    except signing.BadSignature:
        raise StateError("state_invalid", "The sign-in response was not recognised.") from None
    if not isinstance(payload, dict):
        raise StateError()
    try:
        flow = FlowState(**payload)
    except TypeError:
        raise StateError() from None
    if flow.intent not in ("login", "connect"):
        raise StateError()
    if not (flow.state and flow.nonce and flow.code_verifier and flow.redirect_uri):
        raise StateError()
    if flow.intent == "connect" and not flow.user_id:
        raise StateError()
    flow = FlowState(**{**asdict(flow), "next_url": safe_next(flow.next_url)})
    return flow


def cookie_name(provider_id: str) -> str:
    return f"{COOKIE_PREFIX}{provider_id}"


def _cookie_kwargs() -> dict:
    jwt_settings = settings.SIMPLE_JWT
    return {
        "max_age": settings.OAUTH_STATE_MAX_AGE,
        "secure": jwt_settings.get("AUTH_COOKIE_SECURE", False),
        "httponly": True,
        "samesite": "Lax",
        # Sent only to the OAuth endpoints, never to ordinary API calls.
        "path": "/api/auth/oauth/",
    }


def set_state_cookie(response, provider_id: str, flow: FlowState):
    response.set_cookie(cookie_name(provider_id), encode(flow), **_cookie_kwargs())
    return response


def clear_state_cookie(response, provider_id: str):
    response.delete_cookie(
        cookie_name(provider_id),
        path="/api/auth/oauth/",
        samesite="Lax",
    )
    return response
