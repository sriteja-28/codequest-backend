import socket
import time
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .site import public_config


def _timed(check) -> dict:
    """Run one dependency check; never leak hostnames or messages, only the error class."""
    start = time.perf_counter()
    try:
        check()
        return {"ok": True, "ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001 - a health check must report, not raise
        return {"ok": False, "ms": round((time.perf_counter() - start) * 1000, 1), "error": exc.__class__.__name__}


def _check_database() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _check_cache() -> None:
    key = "core:health:ping"
    cache.set(key, "1", 10)
    if cache.get(key) != "1":
        raise RuntimeError("cache read-back mismatch")


def _check_broker() -> None:
    # A TCP connect is enough to prove the broker is reachable and costs no AMQP session.
    parsed = urlparse(settings.RABBITMQ_URL)
    with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5672), timeout=0.5):
        pass


class HealthView(APIView):
    """
    GET /api/health/          dependency checks: database (critical), cache, broker
    GET /api/health/?live=1   liveness only (no dependency calls)

    200 {"status": "ok" | "degraded", ...}: serving; "degraded" means a non-critical
        dependency is down (e.g. broker: submissions return 503 until it is back).
    503 {"status": "down", ...}: the database is unreachable.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        headers = {"Cache-Control": "no-store"}
        if request.query_params.get("live"):
            return Response({"status": "ok"}, headers=headers)

        checks = {
            "database": _timed(_check_database),
            "cache": _timed(_check_cache),
            "broker": _timed(_check_broker),
        }
        if not checks["database"]["ok"]:
            overall = "down"
        elif all(check["ok"] for check in checks.values()):
            overall = "ok"
        else:
            overall = "degraded"
        return Response(
            {"status": overall, "checks": checks, "time": timezone.now().isoformat()},
            status=503 if overall == "down" else 200,
            headers=headers,
        )


class ConfigView(APIView):
    """
    GET /api/config/: public runtime configuration for the frontend:
    site name, maintenance and announcement banners, auth mode and providers,
    feature states ("enabled" | "disabled" | "coming_soon") and limits.
    Identical for every visitor, so it is safe to cache briefly.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(public_config(), headers={"Cache-Control": "public, max-age=30"})
