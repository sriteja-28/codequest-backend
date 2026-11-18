"""Progress dashboard endpoint, cache and submission side effects (B4)."""

from django.utils import timezone

from apps.submissions.models import Submission
from apps.users.models import UserDailyActivity, UserSolvedProblem


def test_progress_endpoint_aggregates_solved_difficulty_and_activity(
    problem_factory, make_user, auth_client
):
    easy_one = problem_factory(difficulty="EASY")
    easy_two = problem_factory(difficulty="EASY")
    medium = problem_factory(difficulty="MEDIUM")
    hard = problem_factory(difficulty="HARD")
    user = make_user()
    UserSolvedProblem.objects.create(user=user, problem=easy_one)
    UserSolvedProblem.objects.create(user=user, problem=medium)
    today = timezone.now().date()
    UserDailyActivity.objects.create(user=user, date=today, submissions=5, accepted=2)
    user.current_streak = 4
    user.best_streak = 9
    user.last_active_date = today
    user.save(update_fields=["current_streak", "best_streak", "last_active_date"])
    Submission.objects.create(
        user=user,
        problem=hard,
        language="python",
        code="class Solution: pass",
        status=Submission.Status.WRONG_ANSWER,
    )

    resp = auth_client(user).get("/api/users/me/progress/")
    assert resp.status_code == 200
    data = resp.json()

    assert data["totals"]["all"] == {"total": 4, "solved": 2}
    assert data["totals"]["EASY"] == {"total": 2, "solved": 1}
    assert data["totals"]["MEDIUM"] == {"total": 1, "solved": 1}
    assert data["totals"]["HARD"] == {"total": 1, "solved": 0}
    assert data["solve_rate"] == 50.0
    assert data["submissions"]["total"] == 1
    assert data["submissions"]["today"] == 5
    assert data["submissions"]["accepted_today"] == 2
    assert data["streak"] == {
        "current": 4,
        "best": 9,
        "last_active_date": today.isoformat(),
    }
    assert len(data["activity"]) == 365
    assert data["activity"][-1] == {
        "date": today.isoformat(),
        "submissions": 5,
        "accepted": 2,
    }
    assert data["sections"]
    assert data["recent_submissions"][0]["problem_slug"] == hard.slug


def test_progress_requires_authentication(auth_client):
    assert auth_client().get("/api/users/me/progress/").status_code == 401


def test_progress_is_cached_and_invalidated_after_a_verdict(
    problem_factory, make_user, auth_client, django_capture_on_commit_callbacks
):
    from django.core.cache import cache

    from apps.submissions.services import finalize_submission
    from apps.users.progress import progress_cache_key

    problem = problem_factory()
    user = make_user()
    client = auth_client(user)
    client.get("/api/users/me/progress/")
    key = progress_cache_key(user.id)
    assert cache.get(key) is not None

    submission = Submission.objects.create(
        user=user,
        problem=problem,
        language="python",
        code="class Solution: pass",
        status=Submission.Status.ACCEPTED,
    )
    with django_capture_on_commit_callbacks(execute=True):
        finalize_submission(submission)

    assert cache.get(key) is None
    activity = UserDailyActivity.objects.get(user=user, date=timezone.now().date())
    assert activity.submissions == 1
    assert activity.accepted == 1

    problem.refresh_from_db()
    assert problem.accepted_submissions == 1

    wrong = Submission.objects.create(
        user=user,
        problem=problem,
        language="python",
        code="class Solution: pass",
        status=Submission.Status.WRONG_ANSWER,
    )
    with django_capture_on_commit_callbacks(execute=True):
        finalize_submission(wrong)
    activity.refresh_from_db()
    assert activity.submissions == 2
    assert activity.accepted == 1
