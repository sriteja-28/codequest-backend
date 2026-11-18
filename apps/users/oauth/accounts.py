"""
Account resolution for social sign-in.

Rules (approved account-linking policy):
  A. A returning (provider, subject) signs into the same user.
  B. A new identity creates one user transactionally; unique (provider, subject)
     and unique email constraints are handled by retrying the resolution.
  C. Matching an email that belongs to a user with another provider does NOT
     auto-merge. The user must sign in their usual way and use the explicit
     Connect flow from the profile page.
  D. An identity that already belongs to another user is refused.
  E. An identity owned by another user is never taken over, even by email.
  F. Legacy accounts without any identity may link once when the provider
     reports a verified email match; the link is recorded in AdminLog.
  G. Banned/inactive accounts are refused before any cookie is issued.

Emails are informational and can be recycled by providers, so they are only
used for the one-time legacy link; every later sign-in matches the permanent
provider subject.
"""

import logging
import re
from dataclasses import replace

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import SocialIdentity, User
from .providers import ProviderProfile

logger = logging.getLogger(__name__)

USERNAME_FALLBACK = "user"
USERNAME_MAX = 50


class AccountError(Exception):
    """Sign-in refused. `code` is stable for the frontend; detail is user-facing."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class SignInResult:
    def __init__(self, user: User, *, created: bool = False, linked_legacy: bool = False):
        self.user = user
        self.created = created
        self.linked_legacy = linked_legacy


def _require_usable(user: User) -> None:
    if not user.is_active:
        raise AccountError("account_disabled", "This account is deactivated.")
    if user.is_banned:
        raise AccountError("account_disabled", "This account is suspended.")


def _require_verified_email(profile: ProviderProfile) -> None:
    if not profile.email or not profile.email_verified:
        raise AccountError(
            "email_unverified",
            "Your sign-in provider did not report a verified email address. "
            "Verify an email with the provider and try again.",
        )


def _normalized(profile: ProviderProfile) -> ProviderProfile:
    """Providers already normalize; fakes and future providers may not."""
    return replace(profile, email=(profile.email or "").strip().lower())


def _audit(identity_pk: int, description: str) -> None:
    from apps.admin_panel.audit import record

    try:
        record(
            action="UPDATE",
            object_type="social_identity",
            object_id=identity_pk,
            description=description,
            source="system",
        )
    except Exception:  # audit logging must never block a sign-in
        logger.warning("could not write identity audit event", exc_info=True)


def username_for(profile: ProviderProfile) -> str:
    """A free username suggested by the provider handle or the email local part."""
    raw = profile.login or profile.email.split("@", 1)[0] or USERNAME_FALLBACK
    base = re.sub(r"[^A-Za-z0-9_.-]", "", raw).strip("._-")[:USERNAME_MAX] or USERNAME_FALLBACK
    candidate = base
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        suffix += 1
        tail = str(suffix)
        candidate = f"{base[: USERNAME_MAX - len(tail)]}{tail}"
    return candidate


def _identity_fields(profile: ProviderProfile) -> dict:
    return {
        "email": profile.email,
        "email_verified": profile.email_verified,
        "display_name": (profile.name or "")[:150],
        "avatar_url": (profile.avatar_url or "")[:500],
    }


def _touch_identity(identity: SocialIdentity, profile: ProviderProfile) -> None:
    """Refresh informational fields without clobbering them with empty values."""
    updates = {"last_login_at": timezone.now()}
    for field, value in _identity_fields(profile).items():
        if value:
            updates[field] = value
    SocialIdentity.objects.filter(pk=identity.pk).update(**updates)
    for field, value in updates.items():
        setattr(identity, field, value)

    # Fill blank profile fields on first sign-in; never overwrite custom values.
    user_updates = {}
    user = identity.user
    if not user.display_name and profile.name:
        user_updates["display_name"] = profile.name[:100]
    if not user.avatar_url and profile.avatar_url:
        user_updates["avatar_url"] = profile.avatar_url[:200]
    if user_updates:
        User.objects.filter(pk=user.pk).update(**user_updates)
        for field, value in user_updates.items():
            setattr(user, field, value)


def _link_legacy(provider_id: str, profile: ProviderProfile, user: User) -> SocialIdentity:
    with transaction.atomic():
        identity = SocialIdentity.objects.create(
            user=user,
            provider=provider_id,
            subject=profile.subject,
            **_identity_fields(profile),
            last_login_at=timezone.now(),
        )
    logger.info("linked %s identity %s to legacy user %s", provider_id, profile.subject, user.pk)
    _audit(
        identity.pk,
        f"Linked {dict(SocialIdentity.Provider.choices).get(provider_id, provider_id)} sign-in "
        f"to an existing account by verified email match (legacy link).",
    )
    return identity


def _create_account(provider_id: str, profile: ProviderProfile) -> SignInResult:
    with transaction.atomic():
        user = User.objects.create_user(
            email=profile.email,
            username=username_for(profile),
            password=None,
            display_name=(profile.name or "")[:100],
            avatar_url=(profile.avatar_url or "")[:200],
        )
        identity = SocialIdentity.objects.create(
            user=user,
            provider=provider_id,
            subject=profile.subject,
            **_identity_fields(profile),
            last_login_at=timezone.now(),
        )
    _audit(identity.pk, f"Created account and linked {provider_id} sign-in.")
    return SignInResult(user, created=True)


def _resolve_sign_in(provider_id: str, profile: ProviderProfile) -> SignInResult:
    identity = (
        SocialIdentity.objects.select_related("user")
        .filter(provider=provider_id, subject=profile.subject)
        .first()
    )
    if identity:
        _require_usable(identity.user)
        _touch_identity(identity, profile)
        return SignInResult(identity.user)

    user = User.objects.filter(email__iexact=profile.email).first()
    if user is None:
        return _create_account(provider_id, profile)

    _require_usable(user)
    existing = list(user.identities.all())
    if existing:
        if any(i.provider == provider_id for i in existing):
            # Same user + same provider, but a different subject: another
            # account at the same provider claims this email. Never take over.
            raise AccountError(
                "identity_conflict",
                "This email is already linked to a different account at the provider.",
            )
        other = existing[0]
        raise AccountError(
            "email_taken",
            f"An account with this email already exists. Sign in with "
            f"{other.get_provider_display()} and connect {provider_id.title()} from your profile.",
        )

    # Legacy account (created before sign-in identities existed) with a
    # provider-verified email: link once and sign in.
    _link_legacy(provider_id, profile, user)
    return SignInResult(user, linked_legacy=True)


def sign_in_with_profile(provider_id: str, profile: ProviderProfile) -> SignInResult:
    """Resolve a verified provider profile to a signable-in user."""
    profile = _normalized(profile)
    _require_verified_email(profile)
    for attempt in (0, 1):
        try:
            return _resolve_sign_in(provider_id, profile)
        except IntegrityError:
            # A concurrent callback won the race for this email or identity.
            # Re-resolve: the second pass finds the now-existing rows.
            if attempt:
                logger.warning("identity resolution conflicted twice for %s", provider_id)
                raise AccountError("sign_in_conflict", "Sign-in conflicted with another request. Please try again.")
    raise AssertionError("unreachable")


def connect_identity(user: User, provider_id: str, profile: ProviderProfile) -> tuple[SocialIdentity, bool]:
    """Attach a provider identity to the signed-in user (explicit Connect flow)."""
    profile = _normalized(profile)
    _require_verified_email(profile)
    _require_usable(user)

    identity = (
        SocialIdentity.objects.select_related("user")
        .filter(provider=provider_id, subject=profile.subject)
        .first()
    )
    if identity:
        if identity.user_id == user.pk:
            _touch_identity(identity, profile)
            return identity, False
        raise AccountError(
            "identity_conflict",
            "This provider account is already linked to another CodeQuest account.",
        )

    if user.identities.filter(provider=provider_id).exists():
        raise AccountError(
            "provider_already_connected",
            f"A {dict(SocialIdentity.Provider.choices).get(provider_id, provider_id)} account is already "
            "connected. Disconnect it first if you want to switch accounts.",
        )

    try:
        with transaction.atomic():
            identity = SocialIdentity.objects.create(
                user=user,
                provider=provider_id,
                subject=profile.subject,
                **_identity_fields(profile),
                last_login_at=timezone.now(),
            )
    except IntegrityError:
        raise AccountError(
            "identity_conflict",
            "This provider account is already linked to another CodeQuest account.",
        ) from None

    _audit(identity.pk, f"Connected {provider_id} sign-in from the profile page.")
    return identity, True


def can_fall_back_to_password(user: User) -> bool:
    """Whether removing every social identity would leave a usable way in."""
    if not user.has_usable_password():
        return False
    return bool(getattr(settings, "DEV_PASSWORD_AUTH", False) or user.is_staff)


def disconnect_identity(user: User, provider_id: str) -> None:
    identity = user.identities.filter(provider=provider_id).first()
    if identity is None:
        raise AccountError("not_connected", "That sign-in method is not connected.")
    if user.identities.count() <= 1 and not can_fall_back_to_password(user):
        raise AccountError(
            "last_credential",
            "You cannot disconnect your only sign-in method. Connect another provider first.",
        )
    identity_pk = identity.pk
    identity.delete()
    _audit(
        identity_pk,
        f"Disconnected {provider_id} sign-in from the profile page.",
    )
