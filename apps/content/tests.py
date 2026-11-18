"""Ad placements (public + admin)."""

from datetime import timedelta

from django.utils import timezone

from apps.content.models import AdCreative, AdPlacement


def _ad(**extra):
    placement, _ = AdPlacement.objects.get_or_create(key="sidebar_left", defaults={"position": "sidebar_left"})
    defaults = {"name": "Banner", "html_snippet": "<b>Go Pro</b>", "link_url": "/upgrade", "plan_target": "FREE"}
    defaults.update(extra)
    return AdCreative.objects.create(placement=placement, **defaults)


def test_placements_for_free_and_pro(make_user, auth_client):
    _ad()
    _ad(name="expired", end_at=timezone.now() - timedelta(days=1))
    _ad(name="off", is_active=False)
    anon = auth_client().get("/api/layout/placements/?route=/problems").json()
    assert [c["name"] for c in anon["placements"][0]["creatives"]] == ["Banner"]
    pro = auth_client(make_user(plan="PRO")).get("/api/layout/placements/").json()
    assert pro["placements"] == []


def test_admin_creatives_toggle_and_link_validation(make_user, auth_client):
    ad = _ad()
    assert auth_client(make_user()).get("/api/layout/admin/creatives/").status_code == 403
    admin = auth_client(make_user(role="ADMIN"))
    assert admin.get("/api/layout/admin/placements/").json()["results"][0]["key"] == "sidebar_left"
    resp = admin.patch(f"/api/layout/admin/creatives/{ad.id}/", {"is_active": False}, format="json")
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    bad = admin.patch(f"/api/layout/admin/creatives/{ad.id}/", {"link_url": "javascript:alert(1)"}, format="json")
    assert bad.status_code == 400
