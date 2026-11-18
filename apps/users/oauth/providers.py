"""
Google (OpenID Connect) and GitHub (OAuth 2.0) sign-in providers.

Each provider builds its authorization URL and turns a returned authorization
code into a ProviderProfile. Credentials come from settings only; a provider
without a client id + secret is reported as not configured.

Security properties:
  * Google's identity comes from the signed OIDC id_token (JWKS verified,
    audience + issuer + nonce checked), never from a userinfo response.
  * GitHub's identity is the numeric account id from /user; the email is the
    verified primary address from /user/emails.
  * Both flows use PKCE (S256) and a signed, one-time state cookie.
"""

import hmac
from dataclasses import dataclass
from urllib.parse import urlencode

import jwt
from django.conf import settings

from .http import OAuthHTTP, ProviderError

PROVIDER_NAMES = (("google", "Google"), ("github", "GitHub"))


@dataclass(frozen=True)
class ProviderProfile:
    """The verified facts a provider gives us about one account."""

    subject: str            # permanent provider account id
    email: str
    email_verified: bool
    name: str = ""
    avatar_url: str = ""
    login: str = ""         # GitHub handle, used to suggest a username


class ProviderNotConfigured(ProviderError):
    def __init__(self, provider_id: str):
        super().__init__("provider_not_configured", f"{provider_id} sign-in has no client id/secret")


def callback_url(provider_id: str) -> str:
    """The frontend route the provider redirects to after authorization."""
    return f"{settings.FRONTEND_URL}/auth/callback/{provider_id}"


def is_configured(provider_id: str) -> bool:
    prefix = provider_id.upper()
    return bool(
        getattr(settings, f"{prefix}_CLIENT_ID", "")
        and getattr(settings, f"{prefix}_CLIENT_SECRET", "")
    )


def configured_providers() -> list[dict]:
    """Providers the UI may offer: credentials are present in this deployment."""
    return [
        {"id": provider_id, "name": name, "enabled": is_configured(provider_id)}
        for provider_id, name in PROVIDER_NAMES
    ]


class BaseProvider:
    id = ""
    name = ""

    def __init__(self, client_id: str, client_secret: str, http: OAuthHTTP | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = http or OAuthHTTP()

    def authorization_url(
        self, *, redirect_uri: str, state: str, nonce: str, code_challenge: str
    ) -> str:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def exchange_code(
        self, *, code: str, redirect_uri: str, code_verifier: str, nonce: str = ""
    ) -> ProviderProfile:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError


class GoogleProvider(BaseProvider):
    id = "google"
    name = "Google"
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
    ISSUERS = ("https://accounts.google.com", "accounts.google.com")
    SCOPE = "openid email profile"

    _jwks_client = None  # shared, caches Google's signing keys

    def __init__(self, client_id: str, client_secret: str, http: OAuthHTTP | None = None, jwks_client=None):
        super().__init__(client_id, client_secret, http)
        self.jwks_client = jwks_client or self._shared_jwks_client()

    @classmethod
    def _shared_jwks_client(cls):
        if cls._jwks_client is None:
            cls._jwks_client = jwt.PyJWKClient(cls.JWKS_URL, cache_keys=True, lifespan=3600, timeout=10)
        return cls._jwks_client

    def authorization_url(self, *, redirect_uri: str, state: str, nonce: str, code_challenge: str) -> str:
        return f"{self.AUTHORIZE_URL}?" + urlencode({
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.SCOPE,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        })

    def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str, nonce: str = "") -> ProviderProfile:
        tokens = self.http.post_form(self.TOKEN_URL, {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code_verifier": code_verifier,
        })
        id_token = tokens.get("id_token") if isinstance(tokens, dict) else None
        if not id_token:
            raise ProviderError("provider_bad_response", "Google did not return an id_token")
        return self._profile_from_id_token(id_token, nonce)

    def _profile_from_id_token(self, id_token: str, expected_nonce: str) -> ProviderProfile:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={"require": ["exp", "iat", "sub", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise ProviderError("provider_bad_token", f"Google id_token rejected: {exc}") from None

        if claims.get("iss") not in self.ISSUERS:
            raise ProviderError("provider_bad_token", "Google id_token has an unexpected issuer")
        if expected_nonce and not hmac.compare_digest(str(claims.get("nonce", "")), expected_nonce):
            raise ProviderError("provider_bad_token", "Google id_token nonce mismatch")

        email = str(claims.get("email") or "").strip().lower()
        verified = claims.get("email_verified")
        return ProviderProfile(
            subject=str(claims.get("sub", "")),
            email=email,
            email_verified=verified is True or str(verified).lower() == "true",
            name=str(claims.get("name") or ""),
            avatar_url=str(claims.get("picture") or ""),
            login="",
        )


class GitHubProvider(BaseProvider):
    id = "github"
    name = "GitHub"
    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    API_USER_URL = "https://api.github.com/user"
    API_EMAILS_URL = "https://api.github.com/user/emails"
    SCOPE = "read:user user:email"

    def authorization_url(self, *, redirect_uri: str, state: str, nonce: str, code_challenge: str) -> str:
        return f"{self.AUTHORIZE_URL}?" + urlencode({
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.SCOPE,
            "state": state,
            # GitHub supports PKCE S256 but not the nonce parameter.
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "allow_signup": "true",
        })

    def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str, nonce: str = "") -> ProviderProfile:
        tokens = self.http.post_form(self.TOKEN_URL, {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        })
        access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
        if not access_token:
            detail = ""
            if isinstance(tokens, dict):
                detail = str(tokens.get("error_description") or tokens.get("error") or "")
            raise ProviderError("provider_bad_response", detail or "GitHub did not return an access token")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        user = self.http.get_json(self.API_USER_URL, headers=headers)
        if not isinstance(user, dict) or not user.get("id"):
            raise ProviderError("provider_bad_response", "GitHub /user returned no account id")

        email, verified = self._pick_email(user, headers)
        login = str(user.get("login") or "")
        return ProviderProfile(
            subject=str(user["id"]),
            email=email,
            email_verified=verified,
            name=str(user.get("name") or login),
            avatar_url=str(user.get("avatar_url") or ""),
            login=login,
        )

    def _pick_email(self, user: dict, headers: dict) -> tuple[str, bool]:
        """Verified primary email, falling back to the public profile address."""
        try:
            emails = self.http.get_json(self.API_EMAILS_URL, headers=headers)
        except ProviderError:
            emails = []
        if isinstance(emails, list):
            verified = [e for e in emails if isinstance(e, dict) and e.get("verified")]
            primary = next((e for e in verified if e.get("primary")), None)
            chosen = primary or (verified[0] if verified else None)
            if chosen:
                return str(chosen.get("email") or "").strip().lower(), True
        profile_email = str(user.get("email") or "").strip().lower()
        return profile_email, False


PROVIDERS = {"google": GoogleProvider, "github": GitHubProvider}


def get_provider(provider_id: str, http: OAuthHTTP | None = None):
    """Build the configured provider, or raise ProviderNotConfigured / ProviderError."""
    cls = PROVIDERS.get(provider_id)
    if cls is None:
        raise ProviderError("unknown_provider", f"Unknown sign-in provider: {provider_id}")
    client_id = getattr(settings, f"{provider_id.upper()}_CLIENT_ID", "")
    client_secret = getattr(settings, f"{provider_id.upper()}_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ProviderNotConfigured(provider_id)
    return cls(client_id=client_id, client_secret=client_secret, http=http)
