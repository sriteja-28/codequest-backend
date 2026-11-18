"""Billing: honest stubs and admin plan changes."""

from django.conf import settings
from django.utils import timezone


def test_plans_reflect_enforced_limits(auth_client, db):
    plans = auth_client().get("/api/billing/plans/").json()
    assert [p["name"] for p in plans] == ["Free", "Pro"]
    assert any(str(settings.AI_HINTS_FREE_DAILY) in f for f in plans[0]["features"])


def test_subscribe_and_cancel_do_not_fake_success(make_user, auth_client):
    user = make_user()
    client = auth_client(user)
    resp = client.post("/api/billing/subscribe/", {"plan_id": 2}, format="json")
    assert resp.status_code == 501
    assert resp.json()["code"] == "coming_soon" and resp.json()["feature"] == "payments"
    assert client.post("/api/billing/cancel/", {}, format="json").status_code == 501
    user.refresh_from_db()
    assert user.plan == "FREE"


def test_admin_plan_change(make_user, auth_client):
    admin, target = make_user(role="ADMIN"), make_user()
    url = f"/api/billing/admin/users/{target.id}/plan/"
    assert auth_client(target).patch(url, {"plan": "PRO"}, format="json").status_code == 403
    resp = auth_client(admin).patch(url, {"plan": "PRO", "days": 30}, format="json")
    assert resp.status_code == 200 and resp.json()["new_plan"] == "PRO"
    target.refresh_from_db()
    assert target.is_pro and (target.plan_expires_at - timezone.now()).days in (29, 30)
    resp = auth_client(admin).patch(url, {"plan": "FREE"}, format="json")
    target.refresh_from_db()
    assert resp.json()["plan_expires_at"] is None and not target.is_pro
    assert auth_client(admin).patch(url, {"plan": "GOLD"}, format="json").status_code == 400
