"""Auth cookies: refresh rotation, logout, banned users, profile, streaks."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

ACCESS = settings.SIMPLE_JWT["AUTH_COOKIE"]
REFRESH = settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"]


def test_public_auth_endpoints_are_gone(db):
    client = APIClient()
    assert client.post("/api/auth/login/", {"email": "a@x.com", "password": "x"}, format="json").status_code == 404
    assert client.post("/api/auth/register/", {"email": "a@x.com"}, format="json").status_code == 404


def test_refresh_rotates_and_blacklists_old_token(make_user):
    user = make_user()
    old = RefreshToken.for_user(user)
    client = APIClient()
    client.cookies[REFRESH] = str(old)
    first = client.post("/api/auth/refresh/")
    assert first.status_code == 200
    new_refresh = first.cookies[REFRESH].value
    assert new_refresh and new_refresh != str(old)

    replay = APIClient()
    replay.cookies[REFRESH] = str(old)
    resp = replay.post("/api/auth/refresh/")
    assert resp.status_code == 401
    assert resp.cookies[REFRESH].value == ""  # cookies cleared

    again = APIClient()
    again.cookies[REFRESH] = new_refresh
    assert again.post("/api/auth/refresh/").status_code == 200


def test_refresh_rejected_for_banned_user(make_user):
    user = make_user()
    client = APIClient()
    client.cookies[REFRESH] = str(RefreshToken.for_user(user))
    user.is_banned = True
    user.save()
    assert client.post("/api/auth/refresh/").status_code == 401


def test_banned_user_cookie_is_anonymous(make_user, auth_client, problem_factory):
    user = make_user()
    client = auth_client(user)
    user.is_banned = True
    user.save()
    assert client.get("/api/auth/me/").status_code == 401
    problem_factory()
    assert client.get("/api/problems/").status_code == 200  # public pages still work


def test_stale_cookie_does_not_break_public_endpoints(db, problem_factory):
    problem_factory()
    client = APIClient()
    client.cookies[ACCESS] = "not-a-jwt"
    assert client.get("/api/problems/").status_code == 200
    assert client.get("/api/auth/me/").status_code == 401


def test_logout_works_without_access_token_and_revokes_refresh(make_user):
    user = make_user()
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.cookies[REFRESH] = str(refresh)
    resp = client.post("/api/auth/logout/")
    assert resp.status_code == 200 and resp.cookies[ACCESS].value == ""
    reuse = APIClient()
    reuse.cookies[REFRESH] = str(refresh)
    assert reuse.post("/api/auth/refresh/").status_code == 401


def test_me_patch_cannot_change_plan_or_role(make_user, auth_client):
    user = make_user()
    resp = auth_client(user).patch("/api/auth/me/", {"plan": "PRO", "role": "ADMIN", "display_name": "X"}, format="json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert (user.plan, user.role, user.display_name) == ("FREE", "USER", "X")


@pytest.mark.parametrize("last_days_ago,start,expected", [(None, 0, 1), (1, 3, 4), (0, 3, 3), (3, 5, 1)])
def test_update_streak(make_user, last_days_ago, start, expected):
    user = make_user()
    user.current_streak = start
    user.best_streak = start
    user.last_active_date = None if last_days_ago is None else timezone.now().date() - timedelta(days=last_days_ago)
    user.save()
    user.update_streak()
    user.refresh_from_db()
    assert user.current_streak == expected and user.best_streak == max(start, expected)
