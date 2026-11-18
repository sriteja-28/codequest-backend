"""Hints (authored, quota-metered) and honest AI stubs."""

from django.test import override_settings


def _hint(client, slug, level=0):
    return client.post("/api/ai/hint/", {"problem_slug": slug, "hint_level": level}, format="json")


def test_hint_contract_matches_frontend(problem_factory, make_user, auth_client):
    problem = problem_factory(hints_md="look at pairs\n---\nuse a hash map")
    data = _hint(auth_client(make_user()), problem.slug).json()
    assert data["hint"] == "look at pairs" and data["level"] == 0
    assert data["has_more"] and data["next_requires_pro"]
    assert data["used_today"] == 1 and data["daily_limit"] >= 1 and data["source"] == "authored"


def test_hint_levels_gated_by_plan(problem_factory, make_user, auth_client):
    problem = problem_factory(hints_md="a\n---\nb")
    assert _hint(auth_client(make_user()), problem.slug, 1).json()["code"] == "pro_required"
    pro = _hint(auth_client(make_user(plan="PRO")), problem.slug, 1).json()
    assert pro["hint"] == "b" and not pro["has_more"]
    assert _hint(auth_client(make_user(plan="PRO")), problem.slug, 2).status_code == 404


@override_settings(AI_HINTS_FREE_DAILY=2)
def test_hint_quota_enforced(problem_factory, make_user, auth_client):
    problem = problem_factory(hints_md="only hint")
    client = auth_client(make_user())
    codes = [_hint(client, problem.slug).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_hint_accepts_problem_id_and_requires_auth(problem_factory, make_user, auth_client):
    problem = problem_factory()
    assert auth_client().post("/api/ai/hint/", {"problem_slug": problem.slug}, format="json").status_code == 401
    resp = auth_client(make_user()).post("/api/ai/hint/", {"problem_id": problem.id}, format="json")
    assert resp.status_code == 200


def test_chat_and_analysis_report_coming_soon(problem_factory, make_user, auth_client):
    problem = problem_factory()
    client = auth_client(make_user())
    resp = client.post("/api/ai/chat/", {"problem_slug": problem.slug, "message": "hi"}, format="json")
    assert resp.status_code == 501 and resp.json() == {
        "detail": resp.json()["detail"], "code": "coming_soon", "feature": "ai_chat",
    }
    explain = client.post("/api/ai/explain-solution/", {"code": "x", "language": "python"}, format="json")
    assert explain.status_code == 501 and explain.json()["feature"] == "ai_explain"
    complexity = client.post("/api/ai/analyze-complexity/", {"code": "x", "language": "python"}, format="json")
    assert complexity.status_code == 501 and complexity.json()["feature"] == "ai_complexity"
    assert client.post("/api/ai/chat/", {"message": "hi"}, format="json").status_code == 400
