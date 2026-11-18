"""
Sign-in tests: OAuth account rules A–E, state handling, dev password login,
profile identity management, admin login buttons and management commands.

No test talks to Google, GitHub or the network: providers are faked at the
view boundary and the provider unit tests use in-memory HTTP/JWKS doubles.
"""

import io
import time
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import Client as DjangoClient
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin_panel.models import AdminLog
from apps.users.models import SocialIdentity, User
from apps.users.oauth import flow
from apps.users.oauth import views as oauth_views
from apps.users.oauth.http import ProviderError
from apps.users.oauth.providers import (
    GitHubProvider,
    GoogleProvider,
    ProviderProfile,
    configured_providers,
)

ACCESS = settings.SIMPLE_JWT["AUTH_COOKIE"]
REFRESH = settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"]
STATE_COOKIE_PATH = "/api/auth/oauth/"


def profile(**overrides) -> ProviderProfile:
    data = {
        "subject": "google-subject-1",
        "email": "new@example.com",
        "email_verified": True,
        "name": "New Person",
        "avatar_url": "https://images.example/avatar.png",
        "login": "",
    }
    data.update(overrides)
    return ProviderProfile(**data)


class FakeProvider:
    def __init__(self, provider_profile: ProviderProfile, error: Exception | None = None):
        self.profile = provider_profile
        self.error = error
        self.auth_kwargs = None
        self.exchange_kwargs = None

    def authorization_url(self, **kwargs):
        self.auth_kwargs = kwargs
        return f"https://provider.test/authorize?state={kwargs['state']}"

    def exchange_code(self, **kwargs):
        self.exchange_kwargs = kwargs
        if self.error:
            raise self.error
        return self.profile


@pytest.fixture
def fake_provider(monkeypatch):
    def _install(provider_profile: ProviderProfile | None = None, error: Exception | None = None):
        fake = FakeProvider(provider_profile or profile(), error)
        monkeypatch.setattr(oauth_views, "get_provider", lambda provider_id, http=None: fake)
        return fake

    return _install


def begin(client: APIClient, provider_id: str = "google", **params):
    response = client.get(f"/api/auth/oauth/{provider_id}/start/", params)
    assert response.status_code == 200, response.content
    raw = response.cookies[flow.cookie_name(provider_id)].value
    assert raw
    return response, flow.decode(raw)


def finish(client: APIClient, state: flow.FlowState, provider_id: str = "google", code: str = "auth-code"):
    return client.post(
        f"/api/auth/oauth/{provider_id}/callback/",
        {"code": code, "state": state.state},
        format="json",
    )


# ─── start endpoint ────────────────────────────────────────────────────────


def test_start_returns_authorization_url_and_signed_state_cookie(db, fake_provider):
    fake = fake_provider()
    client = APIClient()
    response = client.get("/api/auth/oauth/google/start/", {"next": "/problems/two-sum"})

    assert response.status_code == 200
    assert response.json()["authorization_url"].startswith("https://provider.test/authorize")
    cookie = response.cookies[flow.cookie_name("google")]
    assert cookie["httponly"] is True
    assert cookie["path"] == STATE_COOKIE_PATH

    state = flow.decode(cookie.value)
    assert state.intent == "login"
    assert state.next_url == "/problems/two-sum"
    assert state.redirect_uri == f"{settings.FRONTEND_URL}/auth/callback/google"
    assert fake.auth_kwargs["redirect_uri"] == state.redirect_uri
    assert fake.auth_kwargs["code_challenge"] == flow.challenge_for(state)


def test_start_can_redirect_for_admin_login(db, fake_provider):
    fake_provider()
    response = APIClient().get(
        "/api/auth/oauth/google/start/", {"redirect": "1", "next": "/django-admin/"}
    )
    assert response.status_code == 302
    assert response["Location"].startswith("https://provider.test/authorize")
    assert response.cookies[flow.cookie_name("google")].value


def test_start_rejects_unknown_provider(db):
    response = APIClient().get("/api/auth/oauth/twitter/start/")
    assert response.status_code == 404
    assert response.json()["code"] == "unknown_provider"


def test_start_reports_unconfigured_provider(db):
    response = APIClient().get("/api/auth/oauth/google/start/")
    assert response.status_code == 503
    assert response.json()["code"] == "provider_not_configured"


def test_connect_start_requires_authentication(db, fake_provider):
    fake_provider()
    response = APIClient().get("/api/auth/oauth/google/start/", {"intent": "connect"})
    assert response.status_code == 401


# ─── login callback ────────────────────────────────────────────────────────


def test_callback_creates_one_user_and_identity(db, fake_provider):
    fake_provider(profile(subject="g-100", email="New@Example.com", name="New Person"))
    client = APIClient()
    _, state = begin(client, next="/problems/two-sum")

    response = finish(client, state)

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["created"] is True
    assert body["linked_legacy"] is False
    assert body["next"] == "/problems/two-sum"
    assert response.cookies[ACCESS].value and response.cookies[REFRESH].value
    assert response.cookies[ACCESS]["httponly"] is True
    assert response.cookies[flow.cookie_name("google")].value == ""

    user = User.objects.get(email="new@example.com")
    assert user.username == "new"
    assert user.display_name == "New Person"
    assert user.has_usable_password() is False
    assert body["user"]["id"] == user.pk

    identity = user.identities.get()
    assert (identity.provider, identity.subject) == ("google", "g-100")
    assert identity.email_verified is True
    assert identity.last_login_at is not None
    assert User.objects.count() == 1


def test_returning_identity_signs_into_the_same_user(db, make_user, fake_provider):
    user = make_user(email="returning@example.com")
    identity = SocialIdentity.objects.create(
        user=user, provider="google", subject="g-return", email="returning@example.com",
        email_verified=True,
    )
    yesterday = timezone.now().date() - timedelta(days=1)
    user.last_active_date = yesterday
    user.save(update_fields=["last_active_date"])
    assert identity.last_login_at is None

    fake_provider(profile(subject="g-return", email="returning@example.com", name=""))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.pk
    assert response.json()["created"] is False
    user.refresh_from_db()
    identity.refresh_from_db()
    assert user.last_login is not None
    assert user.last_active_date == yesterday  # streak date only moves on a solve
    assert identity.last_login_at is not None
    assert User.objects.count() == 1


def test_new_provider_with_email_of_another_provider_is_not_merged(db, make_user, fake_provider):
    user = make_user(email="shared@example.com")
    SocialIdentity.objects.create(
        user=user, provider="github", subject="gh-1", email="shared@example.com", email_verified=True,
    )
    fake_provider(profile(subject="g-1", email="shared@example.com"))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"
    assert not user.identities.filter(provider="google").exists()
    assert User.objects.count() == 1
    assert ACCESS not in response.cookies


def test_legacy_account_links_once_on_verified_email(db, make_user, fake_provider):
    user = make_user(email="legacy@example.com")
    assert not user.identities.exists()

    fake_provider(profile(subject="g-legacy", email="legacy@example.com"))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 200
    assert response.json()["linked_legacy"] is True
    assert response.json()["user"]["id"] == user.pk
    identity = user.identities.get()
    assert identity.subject == "g-legacy"
    audit = AdminLog.objects.get(object_type="social_identity", object_id=identity.pk)
    assert "legacy" in audit.description.lower()


def test_unverified_email_is_refused(db, fake_provider):
    fake_provider(profile(email_verified=False))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert User.objects.count() == 0
    assert ACCESS not in response.cookies


def test_banned_identity_owner_is_refused_before_cookies(db, make_user, fake_provider):
    user = make_user()
    user.is_banned = True
    user.save()
    SocialIdentity.objects.create(
        user=user, provider="google", subject="g-banned", email=user.email, email_verified=True,
    )
    fake_provider(profile(subject="g-banned", email=user.email))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 403
    assert response.json()["code"] == "account_disabled"
    assert ACCESS not in response.cookies


def test_inactive_legacy_account_is_refused(db, make_user, fake_provider):
    user = make_user(email="inactive@example.com")
    user.is_active = False
    user.save(update_fields=["is_active"])
    fake_provider(profile(subject="g-inactive", email=user.email))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 403
    assert not user.identities.exists()


def test_provider_failure_returns_bad_gateway_and_clears_state(db, fake_provider):
    fake_provider(error=ProviderError("provider_unreachable", "no network"))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 502
    assert response.json()["code"] == "provider_unreachable"
    assert response.cookies[flow.cookie_name("google")].value == ""
    assert ACCESS not in response.cookies


def test_username_collision_gets_a_suffix(db, make_user, fake_provider):
    make_user(username="octocat", email="other@example.com")
    fake_provider(profile(subject="g-octo", email="octo@example.com", login="octocat"))
    client = APIClient()
    _, state = begin(client)
    response = finish(client, state)

    assert response.status_code == 200
    assert User.objects.get(email="octo@example.com").username == "octocat2"


# ─── state handling ────────────────────────────────────────────────────────


def test_missing_state_cookie_is_refused(db):
    response = APIClient().post(
        "/api/auth/oauth/google/callback/", {"code": "x", "state": "y"}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "state_missing"


def test_state_mismatch_is_refused(db, fake_provider):
    fake_provider()
    client = APIClient()
    _, _state = begin(client)
    response = client.post(
        "/api/auth/oauth/google/callback/", {"code": "x", "state": "not-the-state"}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "state_mismatch"
    assert response.cookies[flow.cookie_name("google")].value == ""


def test_tampered_state_cookie_is_refused(db, fake_provider):
    fake_provider()
    client = APIClient()
    response, state = begin(client)
    client.cookies[flow.cookie_name("google")] = response.cookies[flow.cookie_name("google")].value + "x"
    assert finish(client, state).status_code == 400


def test_state_token_is_single_use(db, fake_provider):
    fake_provider(profile(subject="g-once", email="once@example.com"))
    client = APIClient()
    start_response, state = begin(client)
    raw_state_cookie = start_response.cookies[flow.cookie_name("google")].value
    assert finish(client, state).status_code == 200

    replay = APIClient()
    replay.cookies[flow.cookie_name("google")] = raw_state_cookie
    response = finish(replay, state)
    assert response.status_code == 400
    assert response.json()["code"] == "state_reused"
    assert ACCESS not in response.cookies


def test_safe_next_rejects_external_and_auth_targets():
    assert flow.safe_next("/problems/two-sum") == "/problems/two-sum"
    assert flow.safe_next("https://evil.example") == "/"
    assert flow.safe_next("//evil.example") == "/"
    assert flow.safe_next("/\\evil.example") == "/"
    assert flow.safe_next("/auth/login") == "/"
    assert flow.safe_next("javascript:alert(1)") == "/"


# ─── dev password login ────────────────────────────────────────────────────


def test_dev_login_sets_cookies_and_keeps_streak_date(db, make_user, settings):
    settings.DEV_PASSWORD_AUTH = True
    user = make_user(email="dev@example.com")
    yesterday = timezone.now().date() - timedelta(days=1)
    user.last_active_date = yesterday
    user.save(update_fields=["last_active_date"])

    response = APIClient().post(
        "/api/auth/dev-login/",
        {"email": "dev@example.com", "password": "Str0ng-pass-123"},
        format="json",
    )
    assert response.status_code == 200
    assert response.cookies[ACCESS].value and response.cookies[REFRESH].value
    user.refresh_from_db()
    assert user.last_login is not None
    assert user.last_active_date == yesterday


def test_dev_login_is_404_when_disabled(db, make_user, settings):
    settings.DEV_PASSWORD_AUTH = False
    make_user(email="dev@example.com")
    response = APIClient().post(
        "/api/auth/dev-login/",
        {"email": "dev@example.com", "password": "Str0ng-pass-123"},
        format="json",
    )
    assert response.status_code == 404


def test_dev_login_rejects_bad_password_and_banned_user(db, make_user, settings):
    settings.DEV_PASSWORD_AUTH = True
    user = make_user(email="dev@example.com")
    client = APIClient()
    assert client.post(
        "/api/auth/dev-login/", {"email": "dev@example.com", "password": "wrong"}, format="json"
    ).status_code == 400

    user.is_banned = True
    user.save(update_fields=["is_banned"])
    response = client.post(
        "/api/auth/dev-login/",
        {"email": "dev@example.com", "password": "Str0ng-pass-123"},
        format="json",
    )
    assert response.status_code == 400
    assert ACCESS not in response.cookies


def test_staff_sign_in_creates_a_django_admin_session(db, make_user, fake_provider):
    staff = make_user(email="staff@example.com", is_staff=True)
    fake_provider(profile(subject="g-staff", email=staff.email))
    client = APIClient()
    _, state = begin(client)
    assert finish(client, state).status_code == 200
    assert client.get("/django-admin/").status_code == 200


def test_regular_sign_in_does_not_create_an_admin_session(db, fake_provider):
    fake_provider(profile(subject="g-user", email="regular@example.com"))
    client = APIClient()
    _, state = begin(client)
    assert finish(client, state).status_code == 200
    assert client.get("/django-admin/").status_code == 302


# ─── explicit Connect / Disconnect ────────────────────────────────────────


def test_connect_adds_a_second_identity_without_creating_a_user(db, make_user, auth_client, fake_provider):
    user = make_user()
    SocialIdentity.objects.create(
        user=user, provider="github", subject="gh-1", email=user.email, email_verified=True,
    )
    fake_provider(profile(subject="g-connect", email="another@example.com"))
    client = auth_client(user)
    start_response = client.get("/api/auth/oauth/google/start/", {"intent": "connect"})
    assert start_response.status_code == 200
    state = flow.decode(start_response.cookies[flow.cookie_name("google")].value)

    response = finish(client, state)

    assert response.status_code == 201
    assert response.json()["identity"]["provider"] == "google"
    assert response.json()["next"] == "/"
    assert user.identities.count() == 2
    assert User.objects.count() == 1


def test_connect_refuses_identity_owned_by_another_user(db, make_user, auth_client, fake_provider):
    owner = make_user()
    SocialIdentity.objects.create(
        user=owner, provider="google", subject="g-owned", email=owner.email, email_verified=True,
    )
    intruder = make_user()
    fake_provider(profile(subject="g-owned", email="intruder@example.com"))
    client = auth_client(intruder)
    start_response = client.get("/api/auth/oauth/google/start/", {"intent": "connect"})
    state = flow.decode(start_response.cookies[flow.cookie_name("google")].value)
    response = finish(client, state)

    assert response.status_code == 409
    assert response.json()["code"] == "identity_conflict"
    assert not intruder.identities.exists()


def test_connect_refuses_a_second_account_for_the_same_provider(db, make_user, auth_client, fake_provider):
    user = make_user()
    SocialIdentity.objects.create(
        user=user, provider="google", subject="g-first", email=user.email, email_verified=True,
    )
    fake_provider(profile(subject="g-second", email=user.email))
    client = auth_client(user)
    state = flow.decode(
        client.get("/api/auth/oauth/google/start/", {"intent": "connect"})
        .cookies[flow.cookie_name("google")].value
    )
    response = finish(client, state)

    assert response.status_code == 409
    assert response.json()["code"] == "provider_already_connected"


def test_disconnect_refuses_last_credential(db, auth_client):
    user = User.objects.create_user(email="only@example.com", username="only", password=None)
    SocialIdentity.objects.create(
        user=user, provider="google", subject="g-only", email=user.email, email_verified=True,
    )
    response = auth_client(user).delete("/api/auth/identities/google/")
    assert response.status_code == 409
    assert response.json()["code"] == "last_credential"
    assert user.identities.count() == 1


def test_disconnect_removes_identity_and_audits(db, make_user, auth_client):
    user = make_user()
    for provider_id in ("google", "github"):
        SocialIdentity.objects.create(
            user=user, provider=provider_id, subject=f"{provider_id}-1",
            email=user.email, email_verified=True,
        )
    client = auth_client(user)
    response = client.delete("/api/auth/identities/google/")

    assert response.status_code == 204
    assert list(user.identities.values_list("provider", flat=True)) == ["github"]
    audit = AdminLog.objects.filter(object_type="social_identity").latest("created_at")
    assert "Disconnected google" in audit.description


def test_identity_list_requires_auth_and_hides_subjects(db, make_user, auth_client):
    assert APIClient().get("/api/auth/identities/").status_code == 401
    user = make_user()
    SocialIdentity.objects.create(
        user=user, provider="google", subject="g-secret", email=user.email, email_verified=True,
    )
    response = auth_client(user).get("/api/auth/identities/")
    assert response.status_code == 200
    assert response.json()[0]["provider"] == "google"
    assert "subject" not in response.json()[0]


# ─── provider implementations ─────────────────────────────────────────────


class FakeHTTP:
    def __init__(self, token_response, user=None, emails=None, emails_error=None):
        self.token_response = token_response
        self.user = user
        self.emails = emails
        self.emails_error = emails_error
        self.posted = None

    def post_form(self, url, data, headers=None):
        self.posted = (url, data)
        return self.token_response

    def get_json(self, url, headers=None):
        if url.endswith("/user"):
            return self.user
        if url.endswith("/user/emails"):
            if self.emails_error:
                raise self.emails_error
            return self.emails
        raise AssertionError(f"unexpected URL {url}")


class FakeJWKS:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.public_key)


def _google_claims(**overrides):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "google-client-id",
        "sub": "google-123",
        "email": "Person@Example.com",
        "email_verified": True,
        "name": "Person",
        "picture": "https://images.example/p.png",
        "nonce": "nonce-123",
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return claims


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _google_token(rsa_key, **overrides):
    return jwt.encode(
        _google_claims(**overrides), rsa_key, algorithm="RS256", headers={"kid": "test-kid"}
    )


def test_google_authorization_url_has_oidc_pkce_and_nonce():
    provider = GoogleProvider("google-client-id", "secret", jwks_client=FakeJWKS(None))
    url = provider.authorization_url(
        redirect_uri="https://app.example/auth/callback/google",
        state="state-1", nonce="nonce-1", code_challenge="challenge-1",
    )
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == ["openid email profile"]
    assert query["state"] == ["state-1"]
    assert query["nonce"] == ["nonce-1"]
    assert query["code_challenge"] == ["challenge-1"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://app.example/auth/callback/google"]


def test_google_verifies_id_token_and_normalizes_email(rsa_key):
    token = _google_token(rsa_key)
    http = FakeHTTP({"id_token": token})
    provider = GoogleProvider(
        "google-client-id", "secret", http=http, jwks_client=FakeJWKS(rsa_key.public_key())
    )
    result = provider.exchange_code(
        code="c", redirect_uri="https://app.example/auth/callback/google",
        code_verifier="verifier", nonce="nonce-123",
    )
    assert result.subject == "google-123"
    assert result.email == "person@example.com"
    assert result.email_verified is True
    assert result.name == "Person"
    assert http.posted[1]["code_verifier"] == "verifier"


def test_google_rejects_wrong_nonce_and_audience(rsa_key):
    http = FakeHTTP({"id_token": _google_token(rsa_key)})
    provider = GoogleProvider(
        "google-client-id", "secret", http=http, jwks_client=FakeJWKS(rsa_key.public_key())
    )
    with pytest.raises(ProviderError) as nonce_error:
        provider.exchange_code(code="c", redirect_uri="u", code_verifier="v", nonce="wrong")
    assert nonce_error.value.code == "provider_bad_token"

    wrong_audience = GoogleProvider(
        "another-client-id", "secret", http=http, jwks_client=FakeJWKS(rsa_key.public_key())
    )
    with pytest.raises(ProviderError):
        wrong_audience.exchange_code(code="c", redirect_uri="u", code_verifier="v", nonce="nonce-123")


def test_github_exchange_prefers_verified_primary_email():
    http = FakeHTTP(
        {"access_token": "gho_test"},
        user={
            "id": 42, "login": "octocat", "name": None,
            "avatar_url": "https://avatars.example/u/42", "email": "public@example.com",
        },
        emails=[
            {"email": "public@example.com", "primary": True, "verified": False},
            {"email": "42+octocat@users.noreply.github.com", "primary": False, "verified": True},
        ],
    )
    provider = GitHubProvider("github-client-id", "secret", http=http)
    result = provider.exchange_code(
        code="c", redirect_uri="https://app.example/auth/callback/github", code_verifier="verifier"
    )
    assert result.subject == "42"
    assert result.login == "octocat"
    assert result.name == "octocat"
    assert result.email == "42+octocat@users.noreply.github.com"
    assert result.email_verified is True
    assert http.posted[1]["code_verifier"] == "verifier"


def test_github_email_scope_failure_returns_unverified_profile():
    http = FakeHTTP(
        {"access_token": "gho_test"},
        user={"id": 7, "login": "private", "email": "private@example.com"},
        emails_error=ProviderError("provider_rejected", "403"),
    )
    result = GitHubProvider("id", "secret", http=http).exchange_code(
        code="c", redirect_uri="u", code_verifier="v"
    )
    assert result.email == "private@example.com"
    assert result.email_verified is False


def test_github_authorization_url_has_pkce():
    provider = GitHubProvider("github-client-id", "secret")
    url = provider.authorization_url(
        redirect_uri="https://app.example/auth/callback/github",
        state="s", nonce="n", code_challenge="challenge",
    )
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == ["read:user user:email"]
    assert query["code_challenge"] == ["challenge"]
    assert query["code_challenge_method"] == ["S256"]


def test_configured_providers_requires_both_parts(settings):
    assert all(p["enabled"] is False for p in configured_providers())
    settings.GOOGLE_CLIENT_ID = "id"
    assert [p["enabled"] for p in configured_providers() if p["id"] == "google"] == [False]
    settings.GOOGLE_CLIENT_SECRET = "secret"
    assert [p["enabled"] for p in configured_providers() if p["id"] == "google"] == [True]


# ─── Django admin + management commands ──────────────────────────────────


def test_admin_login_offers_only_configured_providers(db, settings):
    settings.GOOGLE_CLIENT_ID = "id"
    settings.GOOGLE_CLIENT_SECRET = "secret"
    settings.GITHUB_CLIENT_ID = ""
    settings.GITHUB_CLIENT_SECRET = ""

    response = DjangoClient().get("/django-admin/login/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "Continue with Google" in content
    assert "Continue with GitHub" not in content
    assert "/api/auth/oauth/google/start/" in content

    settings.GOOGLE_CLIENT_ID = ""
    settings.GOOGLE_CLIENT_SECRET = ""
    content = DjangoClient().get("/django-admin/login/").content.decode()
    assert "Continue with Google" not in content


def test_grant_role_syncs_staff_access(db, make_user):
    user = make_user(email="role@example.com")
    out = io.StringIO()
    call_command("grant_role", "ROLE@example.com", "ADMIN", stdout=out)
    user.refresh_from_db()
    assert user.role == "ADMIN" and user.is_staff is True
    assert "role USER -> ADMIN" in out.getvalue()

    call_command("grant_role", user.email, "USER", stdout=io.StringIO())
    user.refresh_from_db()
    assert user.role == "USER" and user.is_staff is False
    assert AdminLog.objects.filter(object_type="user", object_id=user.pk).count() == 2


def test_grant_role_rejects_unknown_user_and_superuser_without_admin(db, make_user):
    with pytest.raises(CommandError):
        call_command("grant_role", "missing@example.com", "ADMIN", stdout=io.StringIO())

    user = make_user()
    with pytest.raises(CommandError):
        call_command("grant_role", user.email, "USER", superuser=True, stdout=io.StringIO())


def test_report_duplicate_emails(db, make_user):
    first = make_user(email="Dup@Example.com")
    second = make_user(email="dup@example.com")
    SocialIdentity.objects.create(
        user=first, provider="google", subject="g-1", email=second.email, email_verified=True,
    )

    out = io.StringIO()
    call_command("report_duplicate_emails", stdout=out)
    text = out.getvalue()
    assert "duplicate email dup@example.com" in text
    assert "cross-account identity email" in text
    assert "1 case-variant duplicate email(s), 1 cross-account identity email(s)" in text

    with pytest.raises(CommandError):
        call_command("report_duplicate_emails", "--fail", stdout=io.StringIO())
