"""Problem catalogue: listing, ordering, PRO gating, editorial locking, admin."""

from datetime import timedelta

from django.utils import timezone

from apps.problems.models import Problem, Solution


def test_list_and_detail_hide_hidden_test_cases(problem_factory, auth_client):
    problem = problem_factory(samples=1, hidden=2)
    client = auth_client()
    listing = client.get("/api/problems/").json()
    assert listing["count"] == 1
    detail = client.get(f"/api/problems/{problem.slug}/").json()
    assert len(detail["sample_test_cases"]) == 1
    assert "starter_code_python" in detail


def test_ordering_by_acceptance_rate_and_difficulty(problem_factory, auth_client):
    # Regression: ?ordering=acceptance_rate raised FieldError (HTTP 500).
    hard = problem_factory(difficulty="HARD", total_submissions=10, accepted_submissions=1)
    easy = problem_factory(difficulty="EASY", total_submissions=4, accepted_submissions=4)
    medium = problem_factory(difficulty="MEDIUM")
    client = auth_client()
    resp = client.get("/api/problems/?ordering=-acceptance_rate")
    assert resp.status_code == 200
    assert [p["slug"] for p in resp.json()["results"]] == [easy.slug, hard.slug, medium.slug]
    by_diff = client.get("/api/problems/?ordering=difficulty").json()["results"]
    assert [p["difficulty"] for p in by_diff] == ["EASY", "MEDIUM", "HARD"]


def test_page_size_supported_for_catalogue(problem_factory, auth_client):
    for _ in range(25):
        problem_factory()
    data = auth_client().get("/api/problems/?page_size=1000").json()
    assert data["count"] == 25 and len(data["results"]) == 25


def test_pro_problem_listed_but_detail_gated(problem_factory, make_user, auth_client):
    problem = problem_factory(visibility="PRO")
    anon = auth_client()
    assert anon.get("/api/problems/").json()["results"][0]["visibility"] == "PRO"
    resp = anon.get(f"/api/problems/{problem.slug}/")
    assert resp.status_code == 403 and resp.json()["code"] == "pro_required"
    assert "statement_md" not in resp.json()
    assert auth_client(make_user()).get(f"/api/problems/{problem.slug}/").status_code == 403
    assert auth_client(make_user(plan="PRO")).get(f"/api/problems/{problem.slug}/").status_code == 200
    expired = make_user(plan="PRO", plan_expires_at=timezone.now() - timedelta(days=1))
    assert auth_client(expired).get(f"/api/problems/{problem.slug}/").status_code == 403
    assert auth_client(make_user(role="ADMIN")).get(f"/api/problems/{problem.slug}/").status_code == 200


def test_unpublished_problem_not_visible(problem_factory, auth_client):
    problem = problem_factory(is_published=False)
    assert auth_client().get(f"/api/problems/{problem.slug}/").status_code == 404


def test_pro_editorial_locked_for_free_users(problem_factory, make_user, auth_client):
    problem = problem_factory()
    Solution.objects.create(problem=problem, title="Opt", approach_summary_md="secret " * 100,
                            code_python="print('solution')", visibility="PRO")
    locked = auth_client(make_user()).get(f"/api/problems/{problem.slug}/solutions/").json()[0]
    assert locked["is_locked"] and locked["code_python"] == ""
    unlocked = auth_client(make_user(plan="PRO")).get(f"/api/problems/{problem.slug}/solutions/").json()[0]
    assert not unlocked["is_locked"] and unlocked["code_python"]


def test_editorial_locked_during_live_contest(problem_factory, make_user, auth_client):
    from apps.contests.models import Contest, ContestProblem

    problem = problem_factory()
    Solution.objects.create(problem=problem, title="Free", approach_summary_md="idea", code_python="x=1")
    now = timezone.now()
    contest = Contest.objects.create(name="Live", slug="live", start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=1))
    ContestProblem.objects.create(contest=contest, problem=problem)
    sol = auth_client(make_user(plan="PRO")).get(f"/api/problems/{problem.slug}/solutions/").json()[0]
    assert sol["is_locked"] and sol["code_python"] == "" and sol["approach_summary_md"] == ""
    admin_view = auth_client(make_user(role="ADMIN")).get(f"/api/problems/{problem.slug}/solutions/").json()[0]
    assert not admin_view["is_locked"]


def test_admin_problem_crud_requires_admin(problem_factory, make_user, auth_client):
    problem = problem_factory()
    assert auth_client(make_user()).get("/api/problems/admin/problems/").status_code == 403
    admin = auth_client(make_user(role="ADMIN"))
    rows = admin.get("/api/problems/admin/problems/").json()["results"]
    assert rows[0]["test_case_count"] == problem.test_cases.count()
    detail = admin.get(f"/api/problems/admin/problems/{problem.slug}/").json()
    assert detail["starter_code_python"]
    resp = admin.patch(f"/api/problems/admin/problems/{problem.slug}/", {"is_published": False}, format="json")
    assert resp.status_code == 200
    assert not Problem.objects.get(pk=problem.pk).is_published
    created = admin.post(f"/api/problems/admin/problems/{problem.slug}/testcases/",
                         {"input_data": "1 1", "expected_output": "2", "is_sample": False, "is_hidden": True}, format="json")
    assert created.status_code == 201, created.content


def test_admin_create_generates_unique_slugs(problem_factory, make_user, auth_client):
    admin = auth_client(make_user(role="ADMIN"))
    payload = {"difficulty": "EASY", "statement_md": "Add two numbers.", "compare_mode": "EXACT"}
    first = admin.post("/api/problems/admin/problems/", {**payload, "title": "Two Sum!"}, format="json")
    assert first.status_code == 201, first.content
    assert first.json()["slug"] == "two-sum"
    second = admin.post("/api/problems/admin/problems/", {**payload, "title": "Two Sum"}, format="json")
    assert second.status_code == 201, second.content
    assert second.json()["slug"] == "two-sum-2"


def test_section_prerequisites_reject_self_and_cycles(make_user, auth_client):
    from apps.problems.models import Section

    admin = auth_client(make_user(role="ADMIN"))
    a = admin.post("/api/problems/admin/sections/", {"name": "AA", "display_name": "Aa"}, format="json").json()
    b = admin.post("/api/problems/admin/sections/", {"name": "BB", "display_name": "Bb"}, format="json").json()
    assert admin.patch(f"/api/problems/admin/sections/{b['id']}/", {"prerequisite_ids": [a["id"]]},
                       format="json").status_code == 200
    # a now depends on b (which depends on a): closing that loop is a cycle.
    assert admin.patch(f"/api/problems/admin/sections/{a['id']}/", {"prerequisite_ids": [b["id"]]},
                       format="json").status_code == 400
    assert admin.patch(f"/api/problems/admin/sections/{a['id']}/", {"prerequisite_ids": [a["id"]]},
                       format="json").status_code == 400
    a_row = Section.objects.get(pk=a["id"])
    assert list(a_row.prerequisites.values_list("pk", flat=True)) == []


def test_admin_testcases_validated_against_signature(problem_factory, make_user, auth_client):
    from apps.problems import codegen

    problem = problem_factory()
    problem.function_signature = {
        "name": "twoSum",
        "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
        "return_type": "int",
    }
    problem.starter_code_python = ""
    problem.save(update_fields=["function_signature", "starter_code_python"])
    admin = auth_client(make_user(role="ADMIN"))
    url = f"/api/problems/admin/problems/{problem.slug}/testcases/"

    bad_input = admin.post(url, {"input_data": '{"nums": [1], "target": "x"}', "expected_output": "2"}, format="json")
    assert bad_input.status_code == 400 and "input_data" in bad_input.json()
    bad_expected = admin.post(url, {"input_data": '{"nums": [1], "target": 2}', "expected_output": '{"oops": 1}'},
                              format="json")
    assert bad_expected.status_code == 400 and "expected_output" in bad_expected.json()

    ok = admin.post(url, {"input_data": '{"nums": [1], "target": 2}', "expected_output": "3",
                          "is_sample": True, "is_hidden": False}, format="json")
    assert ok.status_code == 201, ok.content
    # The stored values are exactly what the judge reads: parameter-keyed JSON.
    assert codegen.validate_input(problem.function_signature, ok.json()["input_data"]) is None


def test_seed_starters_are_valid_and_seed_refuses_without_debug(db):
    import pytest
    from django.core.management import CommandError, call_command

    from apps.problems import codegen
    from apps.problems.management.commands.seed_data import PROBLEMS
    from apps.problems.seed_extras import EXTRA_PROBLEMS

    for p in [*PROBLEMS, *EXTRA_PROBLEMS]:
        signature = p["function_signature"]
        starters = codegen.all_starters(signature)
        compile(starters["starter_code_python"], p["slug"], "exec")
        assert "\\[" not in starters["starter_code_java"], "Java starter must not contain illegal escapes"
        assert "split('\n')" not in starters["starter_code_javascript"], "JS starter must not embed a raw newline"
        assert "main" not in starters["starter_code_python"]
    with pytest.raises(CommandError):
        call_command("seed_data")  # test settings have DEBUG=False


def test_seed_with_force_and_refresh(db, settings):
    from django.core.management import call_command

    from apps.users.models import User

    call_command("seed_data", "--force")
    assert Problem.objects.count() == 25
    admin = User.objects.get(email="admin@codequest.dev")
    assert admin.is_admin and admin.is_staff and admin.is_superuser
    Problem.objects.filter(slug="two-sum").update(starter_code_java="broken")
    call_command("seed_data", "--force", "--refresh-starters")
    assert "broken" not in Problem.objects.get(slug="two-sum").starter_code_java
