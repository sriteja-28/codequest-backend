import pytest
from rest_framework.test import APIClient

from apps.core.features import FEATURES, resolve_states


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestHealth:
    def test_liveness_needs_no_dependencies(self, client):
        res = client.get("/api/health/?live=1")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
        assert res["Cache-Control"] == "no-store"

    def test_degraded_when_broker_unreachable(self, client):
        # test settings point RABBITMQ_URL at an unroutable port on purpose
        res = client.get("/api/health/")
        body = res.json()
        assert res.status_code == 200
        assert body["status"] == "degraded"
        assert body["checks"]["database"]["ok"] is True
        assert body["checks"]["cache"]["ok"] is True
        assert body["checks"]["broker"]["ok"] is False
        # only the exception class is exposed, never hosts/ports/messages
        assert set(body["checks"]["broker"]) == {"ok", "ms", "error"}

    def test_ok_when_everything_reachable(self, client, monkeypatch):
        monkeypatch.setattr("apps.core.views._check_broker", lambda: None)
        res = client.get("/api/health/")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_down_when_database_fails(self, client, monkeypatch):
        def boom():
            raise ConnectionError("db gone")

        monkeypatch.setattr("apps.core.views._check_database", boom)
        res = client.get("/api/health/")
        assert res.status_code == 503
        assert res.json()["status"] == "down"
        assert res.json()["checks"]["database"]["error"] == "ConnectionError"

    def test_not_throttled(self, client, settings):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK,
                                   "DEFAULT_THROTTLE_RATES": {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
                                                              "anon": "1/hour"}}
        for _ in range(3):
            assert client.get("/api/health/?live=1").status_code == 200


@pytest.mark.django_db
class TestConfig:
    def test_shape(self, client):
        res = client.get("/api/config/")
        assert res.status_code == 200
        body = res.json()
        assert set(body) >= {"site", "maintenance", "announcement", "auth", "features", "limits", "contests"}
        assert body["site"]["name"] == "CodeQuest"
        assert body["maintenance"]["enabled"] is False
        assert {p["id"] for p in body["auth"]["providers"]} == {"google", "github"}
        assert all(p["enabled"] is False for p in body["auth"]["providers"])
        assert body["auth"]["dev_password"] is True  # test settings enable local accounts
        assert set(body["features"]) == {f.key for f in FEATURES}

    def test_unimplemented_features_are_coming_soon(self, client):
        features = client.get("/api/config/").json()["features"]
        assert features["ai_chat"]["state"] == "coming_soon"
        assert "coming soon" in features["ai_chat"]["message"].lower()
        assert features["payments"]["state"] == "coming_soon"
        assert features["ai_hints"]["state"] == "enabled"

    def test_flag_turns_implemented_feature_off_and_cache_invalidates(self, client):
        from apps.content.models import FeatureFlag

        assert client.get("/api/config/").json()["features"]["discussions"]["state"] == "enabled"
        flag = FeatureFlag.objects.create(key="discussions", value=False)
        assert client.get("/api/config/").json()["features"]["discussions"]["state"] == "disabled"
        flag.delete()
        assert client.get("/api/config/").json()["features"]["discussions"]["state"] == "enabled"

    def test_flag_cannot_enable_unimplemented_feature(self, client):
        from apps.content.models import FeatureFlag

        FeatureFlag.objects.create(key="ai_chat", value=True)
        assert client.get("/api/config/").json()["features"]["ai_chat"]["state"] == "coming_soon"

    def test_maintenance_from_platform_settings(self, client):
        from apps.admin_panel.models import PlatformSettings

        PlatformSettings.objects.create(site_name="CQ", maintenance_mode=True, maintenance_message="Back soon")
        body = client.get("/api/config/").json()
        assert body["site"]["name"] == "CQ"
        assert body["maintenance"] == {"enabled": True, "message": "Back soon"}

    def test_survives_cache_outage(self, monkeypatch):
        from apps.core import site

        class BrokenCache:
            def get(self, *_a, **_k):
                raise ConnectionError("redis down")

            set = delete = get

        # Swap only this module's reference: the shared cache proxy is also used by throttles.
        monkeypatch.setattr(site, "cache", BrokenCache())
        config = site.public_config()
        assert config["site"]["name"] == "CodeQuest"
        site.invalidate()  # must not raise either


def test_resolve_states_defaults():
    states = resolve_states({})
    assert all(s["state"] in {"enabled", "coming_soon"} for s in states.values())
    assert resolve_states({"contests": False})["contests"]["state"] == "disabled"
