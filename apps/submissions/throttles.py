"""
Throttles for code execution endpoints.

Rates come from REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]:
  run_free / run_pro       — POST /api/submissions/run-code/
  submit_free / submit_pro — POST /api/submissions/
  burst                    — anti double-click limit shared by both

Plan-aware scope selection happens per request in allow_request(): DRF builds
throttle instances before the request is known, so get_rate() cannot inspect
the user (the previous implementation always fell back to a hard-coded rate).

Rates accept DRF syntax ("10/minute") plus a period multiplier ("3/10s",
"20/5m", "3/10seconds").
"""

import re

from rest_framework.throttling import SimpleRateThrottle

_RATE_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d*)\s*([smhd])[a-z]*\s*$", re.IGNORECASE)
_PERIOD_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_rate_with_multiplier(rate):
    if rate is None:
        return None, None
    match = _RATE_RE.match(rate)
    if not match:
        raise ValueError(f"Invalid throttle rate {rate!r}; expected e.g. '10/minute' or '3/10s'.")
    num, mult, unit = match.groups()
    return int(num), int(mult or 1) * _PERIOD_SECONDS[unit.lower()]


class _UserScopedThrottle(SimpleRateThrottle):
    """Per-user throttle; anonymous requests are not throttled here (the
    endpoints require authentication and the global anon throttle applies)."""

    def parse_rate(self, rate):
        return parse_rate_with_multiplier(rate)

    def select_scope(self, request):
        return self.scope

    def allow_request(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True
        self.scope = self.select_scope(request)
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class _PlanScopedThrottle(_UserScopedThrottle):
    free_scope = ""
    pro_scope = ""

    def select_scope(self, request):
        return self.pro_scope if getattr(request.user, "is_pro", False) else self.free_scope


class RunThrottle(_PlanScopedThrottle):
    """Rate limit for Run endpoint (sample test cases only)"""

    scope = free_scope = "run_free"
    pro_scope = "run_pro"


class SubmitThrottle(_PlanScopedThrottle):
    """Rate limit for Submit endpoint (full judge)"""

    scope = free_scope = "submit_free"
    pro_scope = "submit_pro"


class BurstThrottle(_UserScopedThrottle):
    """Prevent rapid-fire clicks (shared by run and submit)."""

    scope = "burst"
