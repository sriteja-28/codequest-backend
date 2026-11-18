"""Admin API: permissions, stats contract, user management."""

from datetime import timedelta

from django.utils import timezone

from apps.admin_panel.models import AdminLog
from apps.submissions.models import Submission


def test_admin_endpoints_require_admin(make_user, auth_client):
    for url in ("/api/admin/users/", "/api/admin/stats/overview/", "/api/admin/stats/problems/",
                "/api/admin/discussions/flags/", "/api/admin/settings/", "/api/admin/features/", "/api/admin/audit-log/"):
        assert auth_client().get(url).status_code == 401, url
        assert auth_client(make_user()).get(url).status_code == 403, url


def test_stats_overview_shape(make_user, auth_client, problem_factory):
    admin = make_user(role="ADMIN")
    make_user(plan="PRO")
    make_user(plan="PRO", plan_expires_at=timezone.now() - timedelta(days=1))  # expired => free
    problem = problem_factory()
    user = make_user()
    Submission.objects.create(user=user, problem=problem, language="python", code="x", status="ACCEPTED")
    Submission.objects.create(user=user, problem=problem, language="python", code="x", status="WRONG_ANSWER")
    Submission.objects.create(user=user, problem=problem, language="python", code="x", status="ACCEPTED", is_sample_run=True)
    data = auth_client(admin).get("/api/admin/stats/overview/").json()
    assert data["users"]["total"] == 4 and data["users"]["pro"] == 1 and data["users"]["free"] == 3
    assert data["submissions"]["total"] == 2 and data["submissions"]["today"] == 2
    assert data["submissions"]["acceptance_rate_today"] == 50.0
    assert len(data["submissions"]["per_day"]) == 14 and data["submissions"]["per_day"][-1]["count"] == 2
    assert data["platform"]["total_problems"] == 1


def test_user_list_filters_and_pagination(make_user, auth_client):
    admin = make_user(role="ADMIN", username="boss")
    make_user(username="alice", plan="PRO")
    make_user(username="bob")
    client = auth_client(admin)
    data = client.get("/api/admin/users/").json()
    assert data["count"] == 3 and "results" in data
    assert [u["username"] for u in client.get("/api/admin/users/?plan=PRO").json()["results"]] == ["alice"]
    assert [u["username"] for u in client.get("/api/admin/users/?search=bo").json()["results"]] == ["bob", "boss"]


def test_ban_unban_and_self_protection(make_user, auth_client):
    admin = make_user(role="ADMIN")
    target = make_user()
    client = auth_client(admin)
    resp = client.patch(f"/api/admin/users/{target.id}/", {"is_banned": True, "banned_reason": "spam"}, format="json")
    assert resp.status_code == 200 and resp.json()["is_banned"]
    resp = client.patch(f"/api/admin/users/{target.id}/", {"is_banned": False}, format="json")
    assert resp.json()["banned_reason"] == ""
    assert client.patch(f"/api/admin/users/{admin.id}/", {"role": "USER"}, format="json").status_code == 400
    assert client.patch(f"/api/admin/users/{admin.id}/", {"is_banned": True}, format="json").status_code == 400
    # plan is not writable here (billing endpoint owns it)
    client.patch(f"/api/admin/users/{target.id}/", {"plan": "PRO"}, format="json")
    target.refresh_from_db()
    assert target.plan == "FREE"


def test_settings_post_is_not_a_fake_success(make_user, auth_client):
    client = auth_client(make_user(role="ADMIN"))
    assert client.get("/api/admin/settings/").status_code == 200
    assert client.post("/api/admin/settings/", {"site_name": "x", "maintenance_mode": True, "max_problem_limit": 1},
                       format="json").status_code == 405


def test_settings_patch_is_audited_and_reflected_in_config(make_user, auth_client):
    admin = make_user(role="ADMIN")
    client = auth_client(admin)
    resp = client.patch("/api/admin/settings/",
                        {"announcement_text": "New lists are live!", "announcement_level": "success"},
                        format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["announcement_text"] == "New lists are live!"
    row = AdminLog.objects.get(action="UPDATE", object_type="platform_settings")
    assert row.source == "api" and row.admin_id == admin.id
    assert "announcement_text" in row.changes
    config = client.get("/api/config/").json()
    assert config["announcement"] == {"text": "New lists are live!", "level": "success"}


def test_feature_toggles_roundtrip_and_audit(make_user, auth_client):
    from apps.content.models import FeatureFlag

    client = auth_client(make_user(role="ADMIN"))
    rows = {row["key"]: row for row in client.get("/api/admin/features/").json()["features"]}
    assert rows["ai_hints"]["implemented"] and rows["ai_hints"]["state"] == "enabled"
    assert rows["ai_chat"]["implemented"] is False and rows["ai_chat"]["state"] == "coming_soon"

    resp = client.patch("/api/admin/features/ai_hints/", {"enabled": False}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["state"] == "disabled"
    assert FeatureFlag.objects.filter(key="ai_hints", value=False).exists()
    row = AdminLog.objects.get(object_type="feature", object_id="ai_hints")
    assert row.changes["enabled"] == [None, False] and row.source == "api"

    # Coming-soon features stay coming soon; unknown keys 404.
    assert client.patch("/api/admin/features/ai_chat/", {"enabled": True}, format="json").status_code == 400
    assert client.patch("/api/admin/features/nope/", {"enabled": True}, format="json").status_code == 404

    # Resetting to the default removes the override.
    resp = client.patch("/api/admin/features/ai_hints/", {"enabled": None}, format="json")
    assert resp.status_code == 200 and resp.json()["state"] == "enabled"
    assert not FeatureFlag.objects.filter(key="ai_hints").exists()


def test_audit_log_filters_and_types(make_user, auth_client):
    from apps.admin_panel.audit import record

    admin = make_user(role="ADMIN")
    record(actor=admin, action="CREATE", object_type="problem", object_id=7,
           object_repr="Two Sum", description="Created problem 'Two Sum'")
    record(action="UPDATE", object_type="user", object_id=3, object_repr="user3",
           description="grant_role: USER -> ADMIN", source="system")
    client = auth_client(admin)

    body = client.get("/api/admin/audit-log/").json()
    assert body["count"] == 2
    # Newest first; both rows share a timestamp, so the later row wins.
    assert body["results"][0]["source"] == "system" and body["results"][0]["admin"] is None
    assert body["results"][1]["admin"]["username"] == admin.username
    assert body["results"][1]["object_repr"] == "Two Sum"

    system = client.get("/api/admin/audit-log/?source=system").json()["results"]
    assert len(system) == 1 and system[0]["description"] == "grant_role: USER -> ADMIN"
    assert client.get("/api/admin/audit-log/?search=two sum").json()["count"] == 1
    assert client.get("/api/admin/audit-log/?action=CREATE&object_type=problem").json()["count"] == 1
    assert set(client.get("/api/admin/audit-log/types/").json()["object_types"]) == {"problem", "user"}
