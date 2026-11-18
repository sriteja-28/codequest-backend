"""Admin contest API: participant corrections (durable score adjustments) and
the finalize endpoint's conflict/force path."""

import json
from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.admin_panel.models import AdminLog
from apps.contests.models import Contest, ContestParticipant, ContestProblem
from apps.submissions.models import Submission

KEY = {"HTTP_X_JUDGE_API_KEY": settings.JUDGE_INTERNAL_API_KEY}


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    monkeypatch.setattr("apps.submissions.queue.get_queue_depth", lambda: 0)
    monkeypatch.setattr("apps.submissions.views.publish_submission_job", lambda **kw: True)


def _contest(slug, *, start, end, problems=(), **extra):
    contest = Contest.objects.create(name=slug.title(), slug=slug, start_at=start, end_at=end, **extra)
    for index, problem in enumerate(problems):
        ContestProblem.objects.create(contest=contest, problem=problem, order_index=index, score=100 * (index + 1))
    return contest


def _queued(user, problem, contest, created_at):
    sub = Submission.objects.create(
        user=user, problem=problem, contest=contest, language="python", code="x",
        status=Submission.Status.QUEUED,
    )
    Submission.objects.filter(pk=sub.pk).update(created_at=created_at)
    sub.refresh_from_db()
    return sub


def _verdict(client, sub, status):
    tc = sub.problem.test_cases.first()
    payload = {"status": status, "results": [{"test_case_id": tc.id, "status": status}]}
    return client.post(f"/api/submissions/{sub.id}/judge-callback/", data=json.dumps(payload),
                       content_type="application/json", **KEY)


def test_score_adjustment_survives_later_verdicts(make_user, auth_client, problem_factory):
    now = timezone.now()
    problem = problem_factory()
    contest = _contest("adjusted", start=now - timedelta(hours=2), end=now - timedelta(hours=1),
                       problems=[problem])
    corrected, other = make_user(), make_user()
    ContestParticipant.objects.create(contest=contest, user=corrected)
    ContestParticipant.objects.create(contest=contest, user=other)
    client = auth_client(make_user(role="ADMIN"))

    resp = client.patch(f"/api/contests/admin/contests/adjusted/participants/{corrected.id}/",
                        {"score_adjustment": 50, "adjustment_reason": "Judge lost the first accept"},
                        format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["final_score"] == 50 and resp.json()["rank"] == 1
    assert resp.json()["adjustment_reason"] == "Judge lost the first accept"
    row = AdminLog.objects.get(object_type="contest_participant", object_id=str(corrected.id))
    assert row.action == "UPDATE" and "Adjusted" in row.description
    assert "score_adjustment" in row.changes

    # A later verdict adds solved points on top of the durable correction.
    sub = _queued(corrected, problem, contest, contest.start_at + timedelta(minutes=10))
    assert _verdict(auth_client(), sub, "ACCEPTED").status_code == 200
    participant = ContestParticipant.objects.get(contest=contest, user=corrected)
    assert participant.final_score == 150 and participant.score_adjustment == 50
    assert ContestParticipant.objects.get(contest=contest, user=other).rank == 2


def test_finalize_api_conflict_then_force_and_frozen_standings(make_user, auth_client, problem_factory):
    now = timezone.now()
    problem = problem_factory()
    contest = _contest("pended", start=now - timedelta(hours=1), end=now - timedelta(minutes=2),
                       problems=[problem])
    user = make_user()
    ContestParticipant.objects.create(contest=contest, user=user)
    _queued(user, problem, contest, contest.end_at - timedelta(minutes=1))
    client = auth_client(make_user(role="ADMIN"))

    resp = client.post("/api/contests/admin/contests/pended/finalize/", {}, format="json")
    assert resp.status_code == 409, resp.content
    body = resp.json()
    assert body["outcome"] == "judging_pending" and body["pending"] == 1
    assert "still being judged" in body["detail"]
    assert Contest.objects.get(pk=contest.pk).finalized_at is None

    resp = client.post("/api/contests/admin/contests/pended/finalize/", {"force": True}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["outcome"] == "finalized"
    assert Contest.objects.get(pk=contest.pk).finalized_at is not None
    assert AdminLog.objects.filter(description__icontains="Finalized contest 'pended'").exists()

    # Finalized standings are read-only, even for admins.
    resp = client.patch(f"/api/contests/admin/contests/pended/participants/{user.id}/",
                        {"score_adjustment": 10}, format="json")
    assert resp.status_code == 409
