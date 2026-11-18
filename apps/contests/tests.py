"""Contests: visibility, eligibility, scoring idempotency, ranking."""

import json
from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.contests.models import Contest, ContestParticipant, ContestProblem, ContestSubmissionStat
from apps.submissions.models import Submission

KEY = {"HTTP_X_JUDGE_API_KEY": settings.JUDGE_INTERNAL_API_KEY}


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    monkeypatch.setattr("apps.submissions.queue.get_queue_depth", lambda: 0)
    monkeypatch.setattr("apps.submissions.views.publish_submission_job", lambda **kw: True)


@pytest.fixture
def live_contest(problem_factory):
    now = timezone.now()
    contest = Contest.objects.create(name="Sprint", slug="sprint", start_at=now - timedelta(minutes=30),
                                     end_at=now + timedelta(hours=1))
    problem = problem_factory()
    ContestProblem.objects.create(contest=contest, problem=problem, score=100)
    return contest, problem


def _submit(client, contest, problem):
    return client.post("/api/submissions/", {"problem_slug": problem.slug, "language": "python",
                                             "code": "x=1", "contest": contest.id}, format="json")


def _verdict(client, sub, status):
    tc = sub.problem.test_cases.first()
    payload = {"status": status, "results": [{"test_case_id": tc.id, "status": status if status != "COMPILE_ERROR" else "COMPILE_ERROR"}]}
    return client.post(f"/api/submissions/{sub.id}/judge-callback/", data=json.dumps(payload),
                       content_type="application/json", **KEY)


def test_upcoming_contest_hides_problems(problem_factory, auth_client, make_user):
    now = timezone.now()
    contest = Contest.objects.create(name="Soon", slug="soon", start_at=now + timedelta(days=1), end_at=now + timedelta(days=1, hours=2))
    ContestProblem.objects.create(contest=contest, problem=problem_factory())
    data = auth_client().get("/api/contests/soon/").json()
    assert data["status"] == "upcoming" and data["contest_problems"] == [] and data["problems_hidden"]
    admin = auth_client(make_user(role="ADMIN")).get("/api/contests/soon/").json()
    assert len(admin["contest_problems"]) == 1


def test_submission_requires_registration_and_live_window(live_contest, make_user, auth_client):
    contest, problem = live_contest
    user = make_user()
    client = auth_client(user)
    assert _submit(client, contest, problem).status_code == 403  # not registered
    assert client.post(f"/api/contests/{contest.slug}/register/").status_code == 201
    assert client.post(f"/api/contests/{contest.slug}/register/").status_code == 200
    assert _submit(client, contest, problem).status_code == 201

    contest.end_at = timezone.now() - timedelta(minutes=1)
    contest.save()
    assert _submit(auth_client(user), contest, problem).status_code == 403  # ended


def test_problem_must_belong_to_contest(live_contest, make_user, auth_client, problem_factory):
    contest, _ = live_contest
    user = make_user()
    ContestParticipant.objects.create(contest=contest, user=user)
    other = problem_factory()
    assert _submit(auth_client(user), contest, other).status_code == 400


def test_scoring_counts_each_verdict_once(live_contest, make_user, auth_client):
    contest, problem = live_contest
    user = make_user()
    ContestParticipant.objects.create(contest=contest, user=user)
    judge = auth_client()

    wa = Submission.objects.create(user=user, problem=problem, contest=contest, language="python", code="x")
    _verdict(judge, wa, "WRONG_ANSWER")
    _verdict(judge, wa, "WRONG_ANSWER")  # duplicate delivery
    ce = Submission.objects.create(user=user, problem=problem, contest=contest, language="python", code="x")
    _verdict(judge, ce, "COMPILE_ERROR")  # not penalised
    ac = Submission.objects.create(user=user, problem=problem, contest=contest, language="python", code="x")
    _verdict(judge, ac, "ACCEPTED")
    _verdict(judge, ac, "ACCEPTED")

    stat = ContestSubmissionStat.objects.get(participant__user=user)
    assert stat.wrong_attempts == 1 and stat.is_solved and stat.score_awarded == 100
    participant = ContestParticipant.objects.get(user=user)
    assert participant.final_score == 100 and participant.rank == 1
    board = auth_client().get(f"/api/contests/{contest.slug}/leaderboard/").json()["results"][0]
    assert board["penalty_minutes"] == stat.solve_time_minutes + 10


def test_submission_created_outside_window_does_not_score(live_contest, make_user, auth_client):
    contest, problem = live_contest
    user = make_user()
    ContestParticipant.objects.create(contest=contest, user=user)
    late = Submission.objects.create(user=user, problem=problem, contest=contest, language="python", code="x")
    Submission.objects.filter(pk=late.pk).update(created_at=contest.end_at + timedelta(minutes=5))
    late.refresh_from_db()
    _verdict(auth_client(), late, "ACCEPTED")
    assert not ContestSubmissionStat.objects.filter(participant__user=user, is_solved=True).exists()


def test_ranking_uses_penalty_tiebreak(live_contest, make_user, auth_client):
    contest, problem = live_contest
    fast, slow = make_user(), make_user()
    judge = auth_client()
    for user, wrong in ((slow, 2), (fast, 0)):
        ContestParticipant.objects.create(contest=contest, user=user)
        for _ in range(wrong):
            _verdict(judge, Submission.objects.create(user=user, problem=problem, contest=contest, language="python", code="x"), "WRONG_ANSWER")
        _verdict(judge, Submission.objects.create(user=user, problem=problem, contest=contest, language="python", code="x"), "ACCEPTED")
    ranks = dict(ContestParticipant.objects.values_list("user_id", "rank"))
    assert ranks[fast.id] == 1 and ranks[slow.id] == 2


def test_admin_contest_endpoints(make_user, auth_client, live_contest):
    assert auth_client(make_user()).get("/api/contests/admin/contests/").status_code == 403
    admin = auth_client(make_user(role="ADMIN"))
    rows = admin.get("/api/contests/admin/contests/").json()["results"]
    assert rows[0]["status"] == "live" and rows[0]["duration_minutes"] == 90
    now = timezone.now()
    bad = admin.post("/api/contests/admin/contests/", {"name": "X", "slug": "x", "start_at": now.isoformat(),
                                                       "end_at": (now - timedelta(hours=1)).isoformat()}, format="json")
    assert bad.status_code == 400


def test_registration_respects_max_participants(make_user, auth_client, live_contest):
    contest, _ = live_contest
    contest.max_participants = 1
    contest.save()
    assert auth_client(make_user()).post(f"/api/contests/{contest.slug}/register/").status_code == 201
    assert auth_client(make_user()).post(f"/api/contests/{contest.slug}/register/").status_code == 400
