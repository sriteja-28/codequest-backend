"""
Public, cache-backed site configuration (GET /api/config/).

Built from three sources:
  * admin_panel.PlatformSettings (one row): site name, announcement and maintenance
    banners, hint quotas, contest recent window (editable at runtime)
  * content.FeatureFlag: runtime on/off switches for implemented features
  * Django settings: auth mode and providers (infrastructure, never stored in the DB)

The DB-backed part is cached for CACHE_TTL seconds and invalidated whenever a
PlatformSettings or FeatureFlag row is saved or deleted, so admin changes show
up immediately. Cache outages never break the endpoint: it falls back to a DB read.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save

from .features import resolve_states

logger = logging.getLogger(__name__)

# Bump the version whenever the cached shape changes (old entries would lack keys).
CACHE_KEY = "core:site-config:v2"
CACHE_TTL = 60


def get_platform_settings():
    """The singleton settings row, or an unsaved instance carrying the model defaults
    (reads never create the row; the admin settings endpoint does)."""
    from apps.admin_panel.models import PlatformSettings

    return PlatformSettings.objects.filter(pk=PlatformSettings.SINGLETON_PK).first() or PlatformSettings()


def _hint_quotas(ps) -> dict:
    """Daily hint quotas: PlatformSettings when set, else the environment defaults."""
    free = ps.ai_hints_free_daily
    pro = ps.ai_hints_pro_daily
    return {
        "hints_free_daily": settings.AI_HINTS_FREE_DAILY if free is None else free,
        "hints_pro_daily": settings.AI_HINTS_PRO_DAILY if pro is None else pro,
    }


def _auth_config() -> dict:
    from apps.users.oauth.providers import configured_providers

    return {
        "providers": configured_providers(),
        "dev_password": bool(getattr(settings, "DEV_PASSWORD_AUTH", False)),
    }


def _build_db_part() -> dict:
    from apps.content.models import FeatureFlag

    ps = get_platform_settings()
    overrides = dict(FeatureFlag.objects.values_list("key", "value"))
    return {
        "site": {"name": ps.site_name, "description": ps.site_description},
        "maintenance": {"enabled": ps.maintenance_mode, "message": ps.maintenance_message},
        "announcement": _announcement(ps),
        "contests": {"recent_days": ps.contest_recent_days},
        "quotas": _hint_quotas(ps),
        "features": resolve_states(overrides),
    }


def _announcement(ps):
    text = (ps.announcement_text or "").strip()
    if not text:
        return None
    return {"text": text, "level": ps.announcement_level or "info"}


def public_config() -> dict:
    try:
        data = cache.get(CACHE_KEY)
    except Exception:  # cache backend down: serve from the DB
        logger.warning("site config cache read failed", exc_info=True)
        data = None
    if data is None:
        data = _build_db_part()
        try:
            cache.set(CACHE_KEY, data, CACHE_TTL)
        except Exception:
            logger.warning("site config cache write failed", exc_info=True)
    return {
        **data,
        "auth": _auth_config(),
        "limits": {"max_code_bytes": settings.MAX_CODE_BYTES},
    }


def contest_recent_days() -> int:
    """How long ended contests stay under 'Recent' (PlatformSettings, cached)."""
    return int(public_config()["contests"]["recent_days"])


def hint_quota(*, pro: bool) -> int:
    """Hints per day for a plan (PlatformSettings or the environment default, cached)."""
    quotas = public_config()["quotas"]
    return int(quotas["hints_pro_daily"] if pro else quotas["hints_free_daily"])


def maintenance() -> dict:
    """{"enabled": bool, "message": str} (cached)."""
    return public_config()["maintenance"]


def invalidate(**_kwargs) -> None:
    try:
        cache.delete(CACHE_KEY)
    except Exception:
        logger.warning("site config cache invalidation failed", exc_info=True)


def settings_changed(**kwargs):
    # Clear now for same-transaction readers, then again after commit so another
    # process cannot leave a cache of the old committed row behind.
    invalidate()
    transaction.on_commit(invalidate)


def _connect_signals() -> None:
    from apps.admin_panel.models import PlatformSettings
    from apps.content.models import FeatureFlag

    for model in (PlatformSettings, FeatureFlag):
        post_save.connect(settings_changed, sender=model, dispatch_uid=f"core-site-config-save-{model.__name__}")
        post_delete.connect(settings_changed, sender=model, dispatch_uid=f"core-site-config-delete-{model.__name__}")


_connect_signals()
