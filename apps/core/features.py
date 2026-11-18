"""
Feature registry: the single answer to "may the UI offer feature X right now?".

Every user-visible capability that can be switched off, or that is not built
yet, is listed here. Its state is one of:

    enabled      the backend serves it
    disabled     implemented, but switched off by an admin (FeatureFlag row)
    coming_soon  not implemented yet; the UI shows a "coming soon" message
                 instead of letting a request fail

An admin toggles an implemented feature at runtime by creating/updating a
`content.FeatureFlag` row whose key matches (Django admin or the admin
dashboard); no deploy is needed. A flag can never turn an unimplemented
feature on, so the UI is never told to offer something that would 501.

Views that sit behind an unimplemented feature answer with
`coming_soon_response(key)` so every client sees the same JSON shape:
    501 {"detail": "...", "code": "coming_soon", "feature": "<key>"}
"""

from dataclasses import dataclass

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission
from rest_framework.response import Response


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    implemented: bool
    default_on: bool = True
    message: str = ""


FEATURES: tuple[Feature, ...] = (
    Feature("ai_hints", "Hints", implemented=True),
    Feature("discussions", "Discuss", implemented=True),
    Feature("contests", "Contests", implemented=True),
    Feature("courses", "Courses", implemented=True),
    Feature("ads", "Sponsored placements", implemented=True),
    Feature(
        "ai_chat", "AI chat", implemented=False,
        message="AI chat is coming soon. Written hints are available now.",
    ),
    Feature(
        "ai_explain", "Explain solution", implemented=False,
        message="AI solution explanations are coming soon.",
    ),
    Feature(
        "ai_complexity", "Complexity analysis", implemented=False,
        message="Automatic complexity analysis is coming soon.",
    ),
    Feature(
        "payments", "Pro checkout", implemented=False,
        message="Online checkout is coming soon. Contact an admin to get Pro access.",
    ),
    Feature(
        "virtual_contests", "Virtual contests", implemented=False,
        message="Virtual contests are coming soon. Past contest problems can be practised from the archive.",
    ),
    Feature(
        "custom_testcases", "Custom test input", implemented=False,
        message="Running your own test input is coming soon. Run uses the example test cases for now.",
    ),
)

FEATURES_BY_KEY = {f.key: f for f in FEATURES}


def resolve_states(flag_overrides: dict[str, bool]) -> dict[str, dict]:
    """Merge registry defaults with FeatureFlag overrides into the public shape."""
    states = {}
    for feature in FEATURES:
        if not feature.implemented:
            state = "coming_soon"
        else:
            on = flag_overrides.get(feature.key, feature.default_on)
            state = "enabled" if on else "disabled"
        states[feature.key] = {
            "state": state,
            "label": feature.label,
            "message": feature.message if state == "coming_soon" else (
                f"{feature.label} is currently turned off." if state == "disabled" else ""
            ),
        }
    return states


def feature_state(key: str) -> str:
    """Current state of one feature ("enabled" | "disabled" | "coming_soon")."""
    from .site import public_config

    return public_config()["features"].get(key, {}).get("state", "disabled")


def coming_soon_response(key: str) -> Response:
    """Uniform 501 for endpoints whose feature is not built yet."""
    feature = FEATURES_BY_KEY.get(key)
    message = feature.message if feature and feature.message else "This feature is coming soon."
    return Response(
        {"detail": message, "code": "coming_soon", "feature": key},
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


def _disabled_body(key: str) -> dict:
    feature = FEATURES_BY_KEY.get(key)
    label = feature.label if feature else key
    return {"detail": f"{label} is currently turned off.", "code": "feature_disabled", "feature": key}


def feature_disabled_response(key: str) -> Response:
    """Uniform 503 for implemented features an admin has switched off."""
    return Response(_disabled_body(key), status=status.HTTP_503_SERVICE_UNAVAILABLE)


class FeatureDisabled(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "feature_disabled"

    def __init__(self, key: str):
        super().__init__(detail=_disabled_body(key))


def is_staff_user(user) -> bool:
    return bool(user is not None and getattr(user, "is_authenticated", False) and getattr(user, "is_admin", False))


def FeatureEnabled(key: str):  # noqa: N802 - used like a permission class
    """DRF permission: 503 feature_disabled while an admin has switched `key` off.
    Admins keep access so they can check a feature before turning it back on."""

    class _FeatureEnabled(BasePermission):
        def has_permission(self, request, view):
            if is_staff_user(getattr(request, "user", None)) or feature_state(key) == "enabled":
                return True
            raise FeatureDisabled(key)

    _FeatureEnabled.__name__ = f"FeatureEnabled[{key}]"
    return _FeatureEnabled


def feature_enabled_for(user, key: str) -> bool:
    """Same rule outside DRF views (consumers, serializers)."""
    return is_staff_user(user) or feature_state(key) == "enabled"


def admin_feature_rows(overrides: dict[str, bool]) -> list[dict]:
    """Registry + overrides for the admin dashboard."""
    states = resolve_states(overrides)
    return [
        {
            "key": feature.key,
            "label": feature.label,
            "implemented": feature.implemented,
            "default_on": feature.default_on,
            "override": overrides.get(feature.key) if feature.implemented else None,
            "state": states[feature.key]["state"],
            "message": feature.message,
        }
        for feature in FEATURES
    ]
