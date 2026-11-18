"""Practice lists, stars, daily problem and section progress (B4)."""

from django.utils import timezone

from apps.problems.models import DailyProblem, ProblemList, ProblemListItem, Section, Star
from apps.users.models import UserSolvedProblem


def test_section_list_has_slugs_counts_and_solved_progress(problem_factory, make_user, auth_client):
    first = problem_factory(difficulty="EASY")
    problem_factory(difficulty="HARD")
    user = make_user()
    UserSolvedProblem.objects.create(user=user, problem=first)

    data = auth_client(user).get("/api/problems/sections/").json()
    section = next(row for row in data["results"] if row["name"] == "ARRAY")
    assert section["slug"] == "array"
    assert section["problem_count"] == 2
    assert section["solved_count"] == 1
    assert section["prerequisites"] == []


def test_section_slug_is_generated_for_admin_created_rows(db):
    section = Section.objects.create(name="Graph Theory", display_name="Graph Theory")
    assert section.slug == "graph-theory"


def test_practice_list_list_and_detail_with_progress(problem_factory, make_user, auth_client):
    one = problem_factory(difficulty="EASY")
    two = problem_factory(difficulty="MEDIUM")
    three = problem_factory(difficulty="HARD")
    practice = ProblemList.objects.create(slug="core", title="Core", description_md="Start here")
    for index, problem in enumerate([one, two, three]):
        ProblemListItem.objects.create(problem_list=practice, problem=problem, order_index=index)

    user = make_user()
    UserSolvedProblem.objects.create(user=user, problem=two)
    client = auth_client(user)

    listing = client.get("/api/problems/lists/").json()["results"]
    assert listing[0]["problem_count"] == 3
    assert listing[0]["solved_count"] == 1
    assert listing[0]["difficulties"] == {"EASY": 1, "MEDIUM": 1, "HARD": 1}

    detail = client.get("/api/problems/lists/core/").json()
    assert [p["slug"] for p in detail["problems"]] == [one.slug, two.slug, three.slug]
    assert [p["is_solved"] for p in detail["problems"]] == [False, True, False]


def test_unpublished_problems_are_hidden_from_practice_lists(problem_factory, auth_client):
    visible = problem_factory()
    hidden = problem_factory(is_published=False)
    practice = ProblemList.objects.create(slug="mixed", title="Mixed")
    ProblemListItem.objects.create(problem_list=practice, problem=visible, order_index=0)
    ProblemListItem.objects.create(problem_list=practice, problem=hidden, order_index=1)

    detail = auth_client().get("/api/problems/lists/mixed/").json()
    assert [p["slug"] for p in detail["problems"]] == [visible.slug]
    assert detail["problem_count"] == 1


def test_star_toggle_and_starred_list(problem_factory, make_user, auth_client):
    problem = problem_factory()
    client = auth_client(make_user())

    assert client.post(f"/api/problems/{problem.slug}/star/").json()["starred"] is True
    assert Star.objects.filter(problem=problem).count() == 1
    assert client.get("/api/problems/starred/").json()["results"][0]["slug"] == problem.slug

    assert client.post(f"/api/problems/{problem.slug}/star/").json()["starred"] is False
    assert Star.objects.filter(problem=problem).count() == 0
    assert client.get("/api/problems/starred/").json()["results"] == []


def test_star_requires_authentication(problem_factory, auth_client):
    problem = problem_factory()
    assert auth_client().post(f"/api/problems/{problem.slug}/star/").status_code == 401


def test_daily_problem_autocreates_once(problem_factory, auth_client):
    problem = problem_factory()
    client = auth_client()
    first = client.get("/api/problems/daily/")
    assert first.status_code == 200
    payload = first.json()
    assert payload["date"] == timezone.now().date().isoformat()
    assert payload["problem"]["slug"] == problem.slug
    assert DailyProblem.objects.count() == 1

    second = client.get("/api/problems/daily/").json()
    assert second["problem"]["slug"] == payload["problem"]["slug"]
    assert DailyProblem.objects.count() == 1


def test_daily_problem_prefers_scheduled_admin_choice(problem_factory, auth_client):
    scheduled = problem_factory()
    problem_factory()
    DailyProblem.objects.create(date=timezone.now().date(), problem=scheduled)
    payload = auth_client().get("/api/problems/daily/").json()
    assert payload["problem"]["slug"] == scheduled.slug
