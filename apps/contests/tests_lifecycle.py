"""Contest lifecycle: list buckets, finalization (freeze + release), lazy
finalization, contest-scoped problem access and the finalize_contests command."""

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.admin_panel.models import AdminLog, PlatformSettings
from apps.contests.finalize import ALREADY, FINALIZED, NOT_ENDED, PENDING, finalize_contest
from apps.contests.models import Contest, ContestParticipant, ContestProblem, ContestSubmissionStat
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


def _slugs(response):
    assert response.status_code == 200, response.content
    return [row["slug"] for row in response.json()["results"]]


def test_list_buckets_split_current_recent_and_archive(db, auth_client):
    now = timezone.now()
    _contest("live", start=now - timedelta(hours=1), end=now + timedelta(hours=1))
    _contest("upcoming", start=now + timedelta(days=1), end=now + timedelta(days=1, hours=2))
    _contest("recent", start=now - timedelta(days=5, hours=2), end=now - timedelta(days=5))
    _contest("old", start=now - timedelta(days=60, hours=2), end=now - timedelta(days=60))
    _contest("private", start=now - timedelta(hours=1), end=now + timedelta(hours=1), is_public=False)
    client = auth_client()

    assert _slugs(client.get("/api/contests/?bucket=current")) == ["live", "upcoming"]
    assert _slugs(client.get("/api/contests/?bucket=recent")) == ["recent"]
    assert _slugs(client.get("/api/contests/?bucket=archive")) == ["old"]
    ended = client.get("/api/contests/?bucket=ended").json()["results"]
    assert [row["slug"] for row in ended] == ["recent", "old"]
    assert all(row["finalized"] for row in ended)  # listing finalized them on the way
    assert {"problem_count", "participant_count", "user_result"} <= set(ended[0])
    assert set(_slugs(client.get("/api/contests/"))) == {"live", "upcoming", "recent", "old"}
    assert _slugs(client.get("/api/contests/?bucket=ended&search=OL")) == ["old"]

    # The recent window is a runtime setting (PlatformSettings, no deploy needed).
    PlatformSettings.objects.create(contest_recent_days=90)
    assert _slugs(client.get("/api/contests/?bucket=recent")) == ["recent", "old"]
    assert _slugs(client.get("/api/contests/?bucket=archive")) == []


def test_finalize_freezes_ranks_and_releases_problems(problem_factory, make_user, auth_client):
    now = timezone.now()
    hidden = problem_factory(is_published=False)
    public = problem_factory()
    contest = _contest("sprint", start=now - timedelta(hours=2), end=now - timedelta(minutes=30),
                       problems=[hidden, public])
    first, second = contest.contest_problems.order_by("order_index")
    leader, runner, idle, cheater = (make_user() for _ in range(4))
    solves = {leader: [(first, 10), (second, 40)], runner: [(first, 20)], idle: [], cheater: [(first, 5), (second, 6)]}
    for user, solved in solves.items():
        participant = ContestParticipant.objects.create(contest=contest, user=user, is_disqualified=user is cheater)
        for link, minute in solved:
            ContestSubmissionStat.objects.create(
                participant=participant, contest_problem=link, is_solved=True, solve_time_minutes=minute,
                score_awarded=link.score, first_solved_at=contest.start_at + timedelta(minutes=minute),
            )
        participant.final_score = sum(link.score for link, _ in solved)
        participant.rank = 99  # stale until finalized
        participant.save()

    result = finalize_contest(contest)
    assert (result.outcome, result.released, result.participants) == (FINALIZED, 1, 4)
    ranks = dict(ContestParticipant.objects.filter(contest=contest).values_list("user_id", "rank"))
    assert ranks == {leader.id: 1, runner.id: 2, idle.id: 3, cheater.id: None}
    hidden.refresh_from_db()
    assert hidden.is_published
    contest.refresh_from_db()
    assert contest.finalized_at is not None
    log = AdminLog.objects.get(object_type="contest", object_id=contest.pk)
    assert log.admin is None and "1 problem(s) released" in log.description
    assert str(log).startswith("system")
    assert finalize_contest(contest).outcome == ALREADY

    # A verdict that lands after finalization no longer changes the standings.
    late = _queued(idle, public, contest, contest.end_at - timedelta(minutes=1))
    assert _verdict(auth_client(), late, "ACCEPTED").status_code == 200
    assert not ContestSubmissionStat.objects.filter(participant__user=idle, is_solved=True).exists()
    assert ContestParticipant.objects.get(contest=contest, user=idle).rank == 3


def test_finalize_waits_for_submissions_still_being_judged(problem_factory, make_user):
    now = timezone.now()
    problem = problem_factory()
    user = make_user()

    just_ended = _contest("just-ended", start=now - timedelta(hours=1), end=now - timedelta(minutes=2),
                          problems=[problem])
    ContestParticipant.objects.create(contest=just_ended, user=user)
    _queued(user, problem, just_ended, just_ended.end_at - timedelta(minutes=1))
    result = finalize_contest(just_ended)
    assert (result.outcome, result.pending) == (PENDING, 1)
    assert Contest.objects.get(pk=just_ended.pk).finalized_at is None
    assert finalize_contest(just_ended, force=True).outcome == FINALIZED

    # Past the grace period the contest is finalized without waiting.
    long_ago = _contest("long-ago", start=now - timedelta(hours=3), end=now - timedelta(hours=2), problems=[problem])
    ContestParticipant.objects.create(contest=long_ago, user=user)
    _queued(user, problem, long_ago, long_ago.end_at - timedelta(minutes=1))
    result = finalize_contest(long_ago)
    assert (result.outcome, result.pending) == (FINALIZED, 1)

    later = _contest("later", start=now + timedelta(hours=1), end=now + timedelta(hours=2))
    assert finalize_contest(later).outcome == NOT_ENDED


def test_detail_finalizes_lazily_and_reports_the_callers_result(problem_factory, make_user, auth_client):
    now = timezone.now()
    problem = problem_factory(is_published=False)
    contest = _contest("weekly", start=now - timedelta(hours=3), end=now - timedelta(hours=1), problems=[problem])
    user = make_user()
    participant = ContestParticipant.objects.create(contest=contest, user=user, final_score=100)
    ContestSubmissionStat.objects.create(
        participant=participant, contest_problem=contest.contest_problems.get(), is_solved=True,
        solve_time_minutes=12, score_awarded=100, first_solved_at=contest.start_at + timedelta(minutes=12),
    )

    body = auth_client(user).get("/api/contests/weekly/").json()
    assert body["status"] == "ended" and body["finalized"] and body["finalized_at"]
    assert body["user_result"] == {"rank": 1, "final_score": 100, "is_disqualified": False}
    assert body["is_registered"] is True
    item = body["contest_problems"][0]
    assert item["practice_available"] is True
    assert (item["user_solved"], item["user_solve_time"]) == (True, 12)
    # Released: now an ordinary practice problem.
    assert auth_client().get(f"/api/problems/{problem.slug}/").status_code == 200
    board = auth_client().get("/api/contests/weekly/leaderboard/").json()["results"]
    assert [row["rank"] for row in board] == [1]
    assert auth_client().get("/api/contests/missing/leaderboard/").status_code == 404


def test_contest_problems_open_with_the_contest(problem_factory, make_user, auth_client):
    now = timezone.now()
    problem = problem_factory(visibility="PRO", is_published=False)
    other = problem_factory()
    contest = _contest("cup", start=now + timedelta(hours=1), end=now + timedelta(hours=3), problems=[problem])
    url = f"/api/contests/cup/problems/{problem.slug}/"
    anon = auth_client()

    # Before the start: hidden from everyone but admins (and never in practice).
    early = anon.get(url)
    assert early.status_code == 403 and early.json()["code"] == "contest_not_started"
    assert auth_client(make_user(role="ADMIN")).get(url).status_code == 200
    assert anon.get(f"/api/problems/{problem.slug}/").status_code == 404

    # Live: anyone may read it, whatever the plan or the publish state.
    Contest.objects.filter(pk=contest.pk).update(start_at=now - timedelta(minutes=5))
    live = anon.get(url)
    assert live.status_code == 200
    body = live.json()
    assert (body["slug"], body["practice_available"], body["next_slug"]) == (problem.slug, False, None)
    assert anon.get(f"/api/contests/cup/problems/{other.slug}/").status_code == 404

    payload = {"problem_slug": problem.slug, "language": "python", "code": "print(1)"}
    runner = auth_client(make_user())
    assert runner.post("/api/submissions/run-code/", payload, format="json").status_code == 400
    run = runner.post("/api/submissions/run-code/", {**payload, "contest": contest.id}, format="json")
    assert run.status_code == 200, run.content
    run_row = Submission.objects.get(pk=run.json()["submission_id"])
    assert run_row.is_sample_run and run_row.contest_id is None  # runs never score

    competitor = auth_client(make_user())
    submit = {**payload, "contest": contest.id}
    assert competitor.post("/api/submissions/", submit, format="json").status_code == 403  # not registered
    assert competitor.post("/api/contests/cup/register/").status_code == 201
    created = competitor.post("/api/submissions/", submit, format="json")
    assert created.status_code == 201, created.content
    assert Submission.objects.get(pk=created.json()["submission_id"]).contest_id == contest.id
    wrong = competitor.post("/api/submissions/", {**submit, "problem_slug": other.slug}, format="json")
    assert wrong.status_code == 400  # not part of the contest

    # Ended: archive view, and the Pro gate applies again (finalization released it).
    Contest.objects.filter(pk=contest.pk).update(start_at=now - timedelta(hours=3), end_at=now - timedelta(hours=1))
    gated = competitor.get(url)
    assert gated.status_code == 403 and gated.json()["code"] == "pro_required"
    pro = auth_client(make_user(plan="PRO")).get(url)
    assert pro.status_code == 200 and pro.json()["practice_available"] is True


def test_finalize_contests_command(db):
    now = timezone.now()
    _contest("a-done", start=now - timedelta(days=2), end=now - timedelta(days=1))
    _contest("b-done", start=now - timedelta(hours=5), end=now - timedelta(hours=4))
    _contest("c-live", start=now - timedelta(hours=1), end=now + timedelta(hours=1))

    out = StringIO()
    call_command("finalize_contests", "--dry-run", stdout=out)
    text = out.getvalue()
    assert "due: a-done" in text and "due: b-done" in text and "c-live" not in text
    assert not Contest.objects.filter(finalized_at__isnull=False).exists()

    out = StringIO()
    call_command("finalize_contests", stdout=out)
    assert "2 of 2 contest(s) finalized." in out.getvalue()
    finalized = set(Contest.objects.filter(finalized_at__isnull=False).values_list("slug", flat=True))
    assert finalized == {"a-done", "b-done"}

    with pytest.raises(CommandError):
        call_command("finalize_contests", "--slug", "c-live")
    out = StringIO()
    call_command("finalize_contests", stdout=out)
    assert "No contests to finalize." in out.getvalue()


def test_unnumbered_problem_detail_has_no_neighbours(problem_factory, auth_client):
    problem = problem_factory(number=None)
    body = auth_client().get(f"/api/problems/{problem.slug}/").json()
    assert body["next_slug"] is None and body["prev_slug"] is None


def test_contest_admin_pages_render(client, make_user):
    admin = make_user(is_staff=True, is_superuser=True, role="ADMIN")
    client.force_login(admin)
    now = timezone.now()
    contest = _contest("panel", start=now - timedelta(hours=1), end=now + timedelta(hours=1))
    assert client.get("/django-admin/contests/contest/").status_code == 200
    assert client.get(f"/django-admin/contests/contest/{contest.pk}/change/").status_code == 200
    assert client.get("/django-admin/contests/contest/add/").status_code == 200


def test_reaped_job_waits_and_late_in_window_verdict_counts(problem_factory, make_user, auth_client, settings):
    from apps.submissions.services import REAPED_MESSAGE

    settings.CONTEST_FINALIZE_GRACE_SECONDS = 900
    now = timezone.now()
    problem, user = problem_factory(is_published=False), make_user()
    contest = _contest("late-judge", start=now - timedelta(hours=2), end=now - timedelta(minutes=1), problems=[problem])
    ContestParticipant.objects.create(contest=contest, user=user)
    sub = _queued(user, problem, contest, contest.end_at - timedelta(minutes=20))
    Submission.objects.filter(pk=sub.pk).update(status="INTERNAL_ERROR", error_message=REAPED_MESSAGE)
    assert finalize_contest(contest, now=now).outcome == PENDING
    assert _verdict(auth_client(), sub, "ACCEPTED").status_code == 200
    assert finalize_contest(contest, now=now).outcome == FINALIZED
    participant = contest.participants.get()
    assert (participant.rank, participant.final_score) == (1, 100)


def test_deadline_and_bucket_boundaries(db, auth_client, monkeypatch):
    now = timezone.now()
    cutoff = now - timedelta(days=30)
    exact_end = _contest("exact-end", start=now - timedelta(hours=1), end=now)
    _contest("exact-cutoff", start=cutoff - timedelta(hours=1), end=cutoff)
    _contest("just-before", start=cutoff - timedelta(hours=1), end=cutoff - timedelta(microseconds=1))
    monkeypatch.setattr("django.utils.timezone.now", lambda: now)
    client = auth_client()
    assert exact_end.status == "live"  # submission window is inclusive at end_at
    assert finalize_contest(exact_end).outcome == NOT_ENDED
    assert _slugs(client.get("/api/contests/?bucket=current")) == ["exact-end"]
    assert _slugs(client.get("/api/contests/?bucket=recent")) == ["exact-cutoff"]
    assert _slugs(client.get("/api/contests/?bucket=archive")) == ["just-before"]


def test_pending_outside_window_does_not_delay_and_exact_grace_freezes(problem_factory, make_user, settings):
    settings.CONTEST_FINALIZE_GRACE_SECONDS = 900
    now = timezone.now()
    problem, user = problem_factory(), make_user()
    contest = _contest("grace", start=now - timedelta(hours=1), end=now - timedelta(minutes=1), problems=[problem])
    _queued(user, problem, contest, contest.start_at - timedelta(seconds=1))
    _queued(user, problem, contest, contest.end_at + timedelta(seconds=1))
    sample = _queued(user, problem, contest, contest.end_at)
    Submission.objects.filter(pk=sample.pk).update(is_sample_run=True)
    assert finalize_contest(contest, now=now).outcome == FINALIZED

    other = _contest("grace-exact", start=now - timedelta(hours=1), end=now - timedelta(minutes=1))
    _queued(user, problem, other, other.end_at)
    deadline = other.end_at + timedelta(seconds=900)
    assert finalize_contest(other, now=deadline - timedelta(microseconds=1)).outcome == PENDING
    assert finalize_contest(other, now=deadline).outcome == FINALIZED


def test_finalization_rechecks_schedule_and_is_idempotent_with_stale_object(db):
    now = timezone.now()
    contest = _contest("rescheduled", start=now - timedelta(hours=2), end=now - timedelta(hours=1))
    Contest.objects.filter(pk=contest.pk).update(end_at=now + timedelta(hours=1))
    assert finalize_contest(contest).outcome == NOT_ENDED
    Contest.objects.filter(pk=contest.pk).update(end_at=now - timedelta(hours=1))
    stale = Contest.objects.get(pk=contest.pk)
    assert finalize_contest(contest).outcome == FINALIZED
    assert finalize_contest(stale).outcome == ALREADY
    assert AdminLog.objects.filter(object_type="contest", object_id=contest.pk).count() == 1


def test_release_policy_private_opt_out_and_shared_future_round(problem_factory):
    now = timezone.now()
    private, held, shared = [problem_factory(is_published=False) for _ in range(3)]
    for slug, problem, extra in [
        ("private-release", private, {"is_public": False}),
        ("held", held, {"release_problems": False}),
        ("shared-first", shared, {}),
    ]:
        _contest(slug, start=now - timedelta(hours=3), end=now - timedelta(hours=2), problems=[problem], **extra)
    future = _contest("shared-last", start=now + timedelta(hours=1), end=now + timedelta(hours=2), problems=[shared])
    for contest in Contest.objects.exclude(pk=future.pk):
        assert finalize_contest(contest).released == 0
    for problem in (private, held, shared):
        problem.refresh_from_db()
        assert not problem.is_published
    assert finalize_contest(future, now=future.end_at + timedelta(seconds=1)).released == 1


def test_out_of_order_verdicts_use_submission_time(problem_factory, make_user, auth_client):
    now = timezone.now()
    problem, user = problem_factory(), make_user()
    contest = _contest("unordered", start=now - timedelta(hours=1), end=now - timedelta(seconds=1), problems=[problem])
    participant = ContestParticipant.objects.create(contest=contest, user=user)
    wrong_first = _queued(user, problem, contest, contest.start_at + timedelta(minutes=5))
    accept_first = _queued(user, problem, contest, contest.start_at + timedelta(minutes=10))
    wrong_later = _queued(user, problem, contest, contest.start_at + timedelta(minutes=15))
    accept_later = _queued(user, problem, contest, contest.start_at + timedelta(minutes=20))
    judge = auth_client()
    for sub, verdict in [(accept_later, "ACCEPTED"), (wrong_later, "WRONG_ANSWER"),
                         (wrong_first, "WRONG_ANSWER"), (accept_first, "ACCEPTED")]:
        assert _verdict(judge, sub, verdict).status_code == 200
    stat = participant.problem_stats.get()
    assert (stat.wrong_attempts, stat.solve_time_minutes, stat.score_awarded) == (1, 10, 100)
    assert finalize_contest(contest).outcome == FINALIZED
    participant.refresh_from_db()
    assert (participant.final_score, participant.rank) == (100, 1)


def test_final_standings_cannot_be_mutated_via_admin(problem_factory, make_user, auth_client):
    now = timezone.now()
    contest = _contest("frozen", start=now - timedelta(hours=2), end=now - timedelta(hours=1))
    user = make_user()
    participant = ContestParticipant.objects.create(contest=contest, user=user)
    finalize_contest(contest)
    client = auth_client(make_user(role="ADMIN"))
    url = f"/api/contests/admin/contests/frozen/participants/{user.pk}/"
    assert client.patch(url, {"final_score": 999}, format="json").status_code == 409
    assert client.delete(url).status_code == 409
    assert client.patch("/api/contests/admin/contests/frozen/", {"end_at": (now + timedelta(hours=1)).isoformat()}, format="json").status_code == 400
    participant.refresh_from_db()
    assert (participant.rank, participant.final_score) == (1, 0)


def test_rest_visibility_matches_contest_problem_access(problem_factory, make_user, auth_client):
    now = timezone.now()
    problem = problem_factory(is_published=False)
    contest = _contest("secret", start=now - timedelta(hours=1), end=now + timedelta(hours=1), is_public=False, problems=[problem])
    for user in [None, make_user()]:
        client = auth_client(user)
        for path in ["", "leaderboard/", f"problems/{problem.slug}/"]:
            assert client.get(f"/api/contests/{contest.slug}/{path}").status_code == 404
    admin = auth_client(make_user(role="ADMIN"))
    assert admin.get("/api/contests/secret/leaderboard/").status_code == 200
    assert admin.get("/api/contests/secret/").status_code == 200


@pytest.mark.django_db(transaction=True)
def test_websocket_visibility_and_lazy_finalization(make_user):
    from apps.submissions.tests import _cookie_for, _ws_scenario

    now = timezone.now()
    hidden = _contest("hidden", start=now - timedelta(hours=1), end=now + timedelta(hours=1), is_public=False)
    for slug in [hidden.slug, "missing"]:
        _, events, closed = _ws_scenario(f"/ws/contests/{slug}/leaderboard/")
        assert events == [] and closed["code"] == 4404
    admin = make_user(role="ADMIN")
    _, events, closed = _ws_scenario("/ws/contests/hidden/leaderboard/", cookie=_cookie_for(admin), expect=2)
    assert closed is None and events[1]["finalized"] is False
    ended = _contest("long-" + "a" * 110, start=now - timedelta(hours=2), end=now - timedelta(hours=1))
    ContestParticipant.objects.create(contest=ended, user=admin)
    _, events, closed = _ws_scenario(f"/ws/contests/{ended.slug}/leaderboard/", expect=2)
    assert closed is None and events[1]["finalized"] is True
    assert events[1]["entries"][0]["rank"] == 1


@pytest.mark.django_db(transaction=True)
def test_websocket_rechecks_visibility_before_broadcast():
    from asgiref.sync import async_to_sync
    from channels.db import database_sync_to_async
    from channels.layers import get_channel_layer
    from channels.testing import WebsocketCommunicator
    from config.asgi import application
    from apps.contests.views import leaderboard_group

    now = timezone.now()
    contest = _contest("revoke", start=now - timedelta(hours=1), end=now + timedelta(hours=1))

    async def run():
        comm = WebsocketCommunicator(application, "/ws/contests/revoke/leaderboard/", headers=[(b"origin", b"http://localhost:3000")])
        assert (await comm.connect())[0]
        await comm.receive_json_from()
        await comm.receive_json_from()
        await database_sync_to_async(lambda: Contest.objects.filter(pk=contest.pk).update(is_public=False))()
        await get_channel_layer().group_send(leaderboard_group("revoke"), {"type": "leaderboard_update", "entries": [{"secret": True}]})
        event = await comm.receive_output()
        assert event == {"type": "websocket.close", "code": 4404}
        await comm.disconnect()

    async_to_sync(run)()


def test_unpublished_contest_hints_follow_contest_access(problem_factory, make_user, auth_client):
    now = timezone.now()
    problem = problem_factory(is_published=False, visibility="PRO")
    contest = _contest("hint-cup", start=now - timedelta(hours=1), end=now + timedelta(hours=1), problems=[problem])
    client = auth_client(make_user())
    payload = {"problem_slug": problem.slug, "hint_level": 0}
    assert client.post("/api/ai/hint/", payload, format="json").status_code == 404
    response = client.post("/api/ai/hint/", {**payload, "contest": contest.pk}, format="json")
    assert response.status_code == 200 and response.json()["source"] == "authored"
    Contest.objects.filter(pk=contest.pk).update(start_at=now + timedelta(minutes=10))
    assert client.post("/api/ai/hint/", {**payload, "contest": contest.pk}, format="json").status_code == 403


def test_discussions_locked_across_direct_routes_until_contest_ends(problem_factory, make_user, auth_client):
    from apps.discussions.models import DiscussionComment, DiscussionThread

    now = timezone.now()
    problem, user = problem_factory(), make_user()
    contest = _contest("discussion-cup", start=now - timedelta(hours=1), end=now + timedelta(hours=1), problems=[problem])
    thread = DiscussionThread.objects.create(problem=problem, author=user, title="Spoiler", content="Answer")
    comment = DiscussionComment.objects.create(thread=thread, author=user, content="Answer")
    client = auth_client(user)
    assert client.get("/api/discuss/threads/").json()["results"] == []
    locked = client.get(f"/api/discuss/problems/{problem.slug}/threads/")
    assert locked.status_code == 403 and locked.json()["code"] == "contest_locked"
    for path in [f"threads/{thread.pk}/", f"threads/{thread.pk}/comments/"]:
        assert client.get(f"/api/discuss/{path}").status_code == 404
    for path in [f"threads/{thread.pk}/upvote/", f"comments/{comment.pk}/upvote/", f"comments/{comment.pk}/accept/"]:
        assert client.post(f"/api/discuss/{path}").status_code == 404
    assert client.post(f"/api/discuss/threads/{thread.pk}/comments/create/", {"body_md": "answer"}, format="json").status_code == 404
    assert client.post(f"/api/discuss/problems/{problem.slug}/threads/create/", {"title": "T", "content": "C"}, format="json").status_code == 403
    Contest.objects.filter(pk=contest.pk).update(end_at=now - timedelta(seconds=1))
    assert client.get(f"/api/discuss/threads/{thread.pk}/").status_code == 200
    problem.is_published = False
    problem.save()
    assert client.get(f"/api/discuss/threads/{thread.pk}/").status_code == 404


def test_release_held_by_private_round_happens_when_that_round_finalizes(problem_factory):
    now = timezone.now()
    problem = problem_factory(is_published=False)
    public = _contest("public-first", start=now - timedelta(hours=3), end=now - timedelta(hours=2), problems=[problem])
    private = _contest("private-later", start=now - timedelta(minutes=30), end=now + timedelta(minutes=30),
                       problems=[problem], is_public=False)
    assert finalize_contest(public).released == 0  # the private round is still live
    problem.refresh_from_db()
    assert not problem.is_published
    # The private round releases nothing itself, but the public round still owes it.
    result = finalize_contest(private, now=private.end_at + timedelta(seconds=1))
    assert (result.outcome, result.released) == (FINALIZED, 1)
    problem.refresh_from_db()
    assert problem.is_published


def test_pending_early_exit_takes_no_locks(problem_factory, make_user, django_assert_max_num_queries):
    now = timezone.now()
    problem, user = problem_factory(), make_user()
    contest = _contest("busy", start=now - timedelta(hours=1), end=now - timedelta(seconds=5), problems=[problem])
    _queued(user, problem, contest, contest.end_at - timedelta(seconds=30))
    with django_assert_max_num_queries(1) as ctx:  # a single COUNT, no SELECT ... FOR UPDATE
        assert finalize_contest(contest).outcome == PENDING
    assert not any("FOR UPDATE" in q["sql"].upper() for q in ctx.captured_queries)


def test_admin_disqualification_reranks_and_rank_is_not_writable(make_user, auth_client):
    now = timezone.now()
    contest = _contest("dq-live", start=now - timedelta(hours=1), end=now + timedelta(hours=1))
    leader, runner = make_user(), make_user()
    ContestParticipant.objects.create(contest=contest, user=leader, final_score=200, rank=1)
    ContestParticipant.objects.create(contest=contest, user=runner, final_score=100, rank=2)
    admin = auth_client(make_user(role="ADMIN"))
    url = f"/api/contests/admin/contests/dq-live/participants/{runner.pk}/"
    assert admin.patch(url, {"rank": 1}, format="json").status_code == 200  # ignored
    assert dict(contest.participants.values_list("user_id", "rank")) == {leader.pk: 1, runner.pk: 2}

    url = f"/api/contests/admin/contests/dq-live/participants/{leader.pk}/"
    body = {"is_disqualified": True, "disqualified_reason": "Shared solutions"}
    assert admin.patch(url, body, format="json").status_code == 200
    assert dict(contest.participants.values_list("user_id", "rank")) == {leader.pk: None, runner.pk: 1}
    assert admin.delete(url).status_code == 204
    assert admin.delete("/api/contests/admin/contests/missing/participants/1/").status_code == 204
