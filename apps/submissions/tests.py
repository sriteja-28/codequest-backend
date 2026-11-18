"""Regression tests for the submission → judge → verdict pipeline."""

import json
from datetime import timedelta

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.utils import timezone
from rest_framework.throttling import SimpleRateThrottle

from apps.problems.models import Problem
from apps.submissions.models import Submission, SubmissionResult
from apps.submissions.services import REAPED_MESSAGE
from apps.submissions.throttles import BurstThrottle, SubmitThrottle, parse_rate_with_multiplier
from apps.users.models import UserSolvedProblem

KEY = {"HTTP_X_JUDGE_API_KEY": settings.JUDGE_INTERNAL_API_KEY}


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """Never touch RabbitMQ: queue depth 0, publish succeeds unless a test says otherwise."""
    monkeypatch.setattr("apps.submissions.queue.get_queue_depth", lambda: 0)
    published = []
    monkeypatch.setattr(
        "apps.submissions.views.publish_submission_job",
        lambda **kw: published.append(kw) or True,
    )
    return published


def _callback(client, sub, payload, **headers):
    return client.post(
        f"/api/submissions/{sub.id}/judge-callback/",
        data=json.dumps(payload), content_type="application/json", **(headers or KEY),
    )


def _verdict(problem, status="ACCEPTED", **extra):
    tcs = list(problem.test_cases.order_by("order_index"))
    result_status = "ACCEPTED" if status == "ACCEPTED" else status
    results = [
        {"test_case_id": tc.id, "status": "ACCEPTED", "actual_output": tc.expected_output, "time_ms": 5, "memory_kb": 900}
        for tc in tcs[:-1]
    ] + [{"test_case_id": tcs[-1].id, "status": result_status, "actual_output": "leak?", "error_output": "trace", "time_ms": 7, "memory_kb": 1000}]
    payload = {"status": status, "runtime_ms": 7, "memory_kb": 1000, "error_message": "", "results": results}
    payload.update(extra)
    return payload


# ─── Submit / Run ─────────────────────────────────────────────────────────────

def test_submit_queues_and_publishes_without_touching_counters(make_user, auth_client, problem_factory, _no_broker):
    user, problem = make_user(), problem_factory()
    resp = auth_client(user).post("/api/submissions/", {"problem_slug": problem.slug, "language": "python", "code": "print(1)"}, format="json")
    assert resp.status_code == 201, resp.content
    sub = Submission.objects.get(id=resp.json()["submission_id"])
    assert sub.status == "QUEUED" and not sub.is_sample_run
    assert _no_broker[0]["run_sample"] is False and _no_broker[0]["problem_id"] == problem.id
    problem.refresh_from_db()
    assert problem.total_submissions == 0  # counted when the verdict arrives


def test_submit_publish_failure_returns_503_and_marks_internal_error(make_user, auth_client, problem_factory, monkeypatch):
    monkeypatch.setattr("apps.submissions.views.publish_submission_job", lambda **kw: False)
    user, problem = make_user(), problem_factory()
    resp = auth_client(user).post("/api/submissions/", {"problem_slug": problem.slug, "language": "python", "code": "x=1"}, format="json")
    assert resp.status_code == 503
    assert "detail" in resp.json() and "error" in resp.json()
    sub = Submission.objects.get(user=user)
    assert sub.status == "INTERNAL_ERROR"
    problem.refresh_from_db()
    assert problem.total_submissions == 0


def test_submit_requires_authentication(problem_factory, auth_client):
    resp = auth_client().post("/api/submissions/", {"problem_slug": problem_factory().slug, "language": "python", "code": "x"}, format="json")
    assert resp.status_code == 401


def test_pro_problem_requires_pro_plan(make_user, auth_client, problem_factory):
    problem = problem_factory(visibility="PRO")
    free = make_user()
    pro = make_user(plan="PRO")
    body = {"problem_slug": problem.slug, "language": "python", "code": "x=1"}
    resp = auth_client(free).post("/api/submissions/", body, format="json")
    assert resp.status_code == 403 and resp.json()["code"] == "pro_required"
    assert auth_client(free).post("/api/submissions/run-code/", body, format="json").status_code == 403
    assert auth_client(pro).post("/api/submissions/", body, format="json").status_code == 201


def test_rejects_unknown_language_empty_and_oversized_code(make_user, auth_client, problem_factory):
    problem = problem_factory()
    url = "/api/submissions/"
    huge = "#" * (settings.MAX_CODE_BYTES + 1)
    bodies = [
        {"problem_slug": problem.slug, "language": "ruby", "code": "x"},
        {"problem_slug": problem.slug, "language": "python", "code": "   "},
        {"problem_slug": problem.slug, "language": "python", "code": huge},
        {"problem_slug": "nope", "language": "python", "code": "x"},
    ]
    for body in bodies:  # fresh user each time: the burst throttle (3/10s) runs before validation
        assert auth_client(make_user()).post(url, body, format="json").status_code == 400, body


def test_run_code_marks_sample_run(make_user, auth_client, problem_factory, _no_broker):
    user, problem = make_user(), problem_factory()
    resp = auth_client(user).post("/api/submissions/run-code/", {"problem_slug": problem.slug, "language": "python", "code": "x=1"}, format="json")
    assert resp.status_code == 200
    sub = Submission.objects.get(id=resp.json()["submission_id"])
    assert sub.is_sample_run and _no_broker[0]["run_sample"] is True
    # Sample runs never appear in history
    assert auth_client(user).get("/api/submissions/history/").json()["count"] == 0


# ─── Judge callback ───────────────────────────────────────────────────────────

@pytest.fixture
def queued(make_user, problem_factory):
    user, problem = make_user(), problem_factory()
    sub = Submission.objects.create(user=user, problem=problem, language="python", code="print(1)")
    return sub


def test_callback_rejects_missing_or_wrong_key(queued, auth_client):
    client = auth_client()
    assert _callback(client, queued, {"status": "RUNNING"}, HTTP_X_JUDGE_API_KEY="").status_code == 403
    assert _callback(client, queued, {"status": "RUNNING"}, HTTP_X_JUDGE_API_KEY="wrong").status_code == 403
    queued.refresh_from_db()
    assert queued.status == "QUEUED"


def test_callback_rejects_unknown_status(queued, auth_client):
    resp = _callback(auth_client(), queued, {"status": "HACKED_STATUS", "runtime_ms": 9})
    assert resp.status_code == 400
    queued.refresh_from_db()
    assert queued.status == "QUEUED" and queued.runtime_ms is None


def test_callback_rejects_test_case_of_another_problem(queued, auth_client, problem_factory):
    other = problem_factory()
    foreign = other.test_cases.first()
    payload = {"status": "WRONG_ANSWER", "results": [{"test_case_id": foreign.id, "status": "WRONG_ANSWER"}]}
    assert _callback(auth_client(), queued, payload).status_code == 400
    queued.refresh_from_db()
    assert queued.status == "QUEUED"


def test_running_callback_sets_judge_started_at(queued, auth_client):
    resp = _callback(auth_client(), queued, {"status": "RUNNING", "results": []})
    assert resp.status_code == 200 and resp.json()["applied"] is True
    queued.refresh_from_db()
    assert queued.status == "RUNNING" and queued.judge_started_at is not None and queued.judge_finished_at is None


def test_terminal_callback_is_applied_once(queued, auth_client):
    client, problem, user = auth_client(), queued.problem, queued.user
    _callback(client, queued, {"status": "RUNNING"})
    first = _callback(client, queued, _verdict(problem, "ACCEPTED"))
    assert first.status_code == 200 and first.json()["applied"] is True

    # Duplicate delivery / replay with a different verdict: acknowledged, ignored.
    second = _callback(client, queued, _verdict(problem, "WRONG_ANSWER"))
    assert second.status_code == 200 and second.json() == {"ok": True, "applied": False, "status": "ACCEPTED"}
    late_running = _callback(client, queued, {"status": "RUNNING"})
    assert late_running.json()["applied"] is False

    queued.refresh_from_db(); problem.refresh_from_db(); user.refresh_from_db()
    assert queued.status == "ACCEPTED" and queued.judge_finished_at is not None
    assert (problem.total_submissions, problem.accepted_submissions) == (1, 1)
    assert problem.acceptance_rate == 100.0
    assert UserSolvedProblem.objects.filter(user=user, problem=problem).count() == 1
    # Regression: problems_solved was computed but never saved.
    assert user.problems_solved == 1
    assert user.current_streak == 1 and user.last_active_date == timezone.now().date()
    assert SubmissionResult.objects.filter(submission=queued).count() == problem.test_cases.count()


def test_wrong_answer_counts_attempt_but_not_solve(queued, auth_client):
    _callback(auth_client(), queued, _verdict(queued.problem, "WRONG_ANSWER"))
    problem = Problem.objects.get(pk=queued.problem_id)
    assert (problem.total_submissions, problem.accepted_submissions) == (1, 0)
    assert not UserSolvedProblem.objects.filter(user=queued.user).exists()


def test_internal_error_and_sample_runs_have_no_side_effects(queued, auth_client, make_user, problem_factory):
    _callback(auth_client(), queued, {"status": "INTERNAL_ERROR", "error_message": "docker down", "results": []})
    problem = Problem.objects.get(pk=queued.problem_id)
    assert problem.total_submissions == 0

    run = Submission.objects.create(user=queued.user, problem=problem, language="python", code="x", is_sample_run=True)
    _callback(auth_client(), run, _verdict(problem, "ACCEPTED"))
    problem.refresh_from_db()
    assert problem.total_submissions == 0
    assert not UserSolvedProblem.objects.filter(user=queued.user).exists()


def test_best_runtime_improves_on_resolve(queued, auth_client):
    _callback(auth_client(), queued, _verdict(queued.problem, "ACCEPTED", runtime_ms=50, memory_kb=5000))
    again = Submission.objects.create(user=queued.user, problem=queued.problem, language="python", code="y")
    _callback(auth_client(), again, _verdict(queued.problem, "ACCEPTED", runtime_ms=20, memory_kb=7000))
    solved = UserSolvedProblem.objects.get(user=queued.user, problem=queued.problem)
    assert (solved.best_runtime_ms, solved.best_memory_kb) == (20, 5000)
    queued.user.refresh_from_db()
    assert queued.user.problems_solved == 1


def test_reaped_submission_accepts_late_real_verdict(queued, auth_client):
    Submission.objects.filter(pk=queued.pk).update(created_at=timezone.now() - timedelta(hours=2))
    from apps.submissions.services import reap_stale_submissions

    assert reap_stale_submissions() == 1
    queued.refresh_from_db()
    assert queued.status == "INTERNAL_ERROR" and queued.error_message == REAPED_MESSAGE
    resp = _callback(auth_client(), queued, _verdict(queued.problem, "ACCEPTED"))
    assert resp.json()["applied"] is True
    queued.refresh_from_db()
    assert queued.status == "ACCEPTED"


def test_detail_reaps_stale_submission(queued, auth_client):
    Submission.objects.filter(pk=queued.pk).update(created_at=timezone.now() - timedelta(hours=2))
    data = auth_client(queued.user).get(f"/api/submissions/{queued.id}/").json()
    assert data["status"] == "INTERNAL_ERROR" and data["error_message"] == REAPED_MESSAGE


def test_reap_command(queued):
    from django.core.management import call_command

    Submission.objects.filter(pk=queued.pk).update(created_at=timezone.now() - timedelta(hours=2))
    call_command("reap_stuck_submissions", "--older-than", "60")
    queued.refresh_from_db()
    assert queued.status == "INTERNAL_ERROR"


# ─── Hidden test data protection ─────────────────────────────────────────────

def test_hidden_results_redacted_for_owner_visible_to_admin(queued, auth_client, make_user):
    problem = queued.problem
    _callback(auth_client(), queued, {"status": "RUNNING"})
    payload = _verdict(problem, "RUNTIME_ERROR", error_message="Traceback...\nValueError: secret-hidden-input 0 100")
    _callback(auth_client(), queued, payload)

    owner = auth_client(queued.user).get(f"/api/submissions/{queued.id}/").json()
    by_hidden = {r["is_hidden"]: r for r in owner["results"]}
    sample, hidden = by_hidden[False], by_hidden[True]
    assert sample["expected_output"] and sample["input_data"] is not None
    for field in ("input_data", "actual_output", "expected_output", "error_output"):
        assert hidden[field] is None, field
    assert "secret-hidden-input" not in json.dumps(owner)
    assert owner["error_message"].startswith("Runtime Error on a hidden test case (ValueError)")
    assert owner["duration_ms"] is not None and owner["duration_ms"] >= 0

    admin = make_user(role="ADMIN")
    full = auth_client(admin).get(f"/api/submissions/{queued.id}/").json()
    hidden_full = next(r for r in full["results"] if r["is_hidden"])
    assert hidden_full["expected_output"] is not None and "secret-hidden-input" in full["error_message"]


def test_other_users_cannot_read_submission(queued, auth_client, make_user):
    assert auth_client(make_user()).get(f"/api/submissions/{queued.id}/").status_code == 404
    assert auth_client().get(f"/api/submissions/{queued.id}/").status_code == 401


# ─── Internal test-case endpoint ─────────────────────────────────────────────

def test_judge_testcases_endpoint(problem_factory, auth_client):
    problem = problem_factory(samples=2, hidden=3)
    url = f"/api/submissions/judge/problems/{problem.id}/testcases/"
    assert auth_client().get(url).status_code == 403
    full = auth_client().get(url, **KEY).json()
    assert len(full["test_cases"]) == 5
    assert full["function_signature"] is None
    assert full["compare_mode"] == "EXACT"
    assert full["float_tolerance"] == 1e-5
    samples = auth_client().get(url + "?sample_only=1", **KEY).json()["test_cases"]
    assert len(samples) == 2 and all(tc["is_sample"] for tc in samples)
    assert auth_client().get("/api/submissions/judge/problems/999999/testcases/", **KEY).status_code == 404


def test_judge_testcases_endpoint_includes_function_mode(problem_factory, auth_client):
    problem = problem_factory(
        function_signature={
            "name": "add",
            "params": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            "return_type": "int",
        },
        compare_mode="UNORDERED",
        float_tolerance=0.001,
    )
    data = auth_client().get(f"/api/submissions/judge/problems/{problem.id}/testcases/", **KEY).json()
    assert data["function_signature"]["name"] == "add"
    assert data["compare_mode"] == "UNORDERED"
    assert data["float_tolerance"] == 0.001


# ─── Throttling ───────────────────────────────────────────────────────────────

def test_parse_rate_with_multiplier():
    assert parse_rate_with_multiplier("3/10s") == (3, 10)
    assert parse_rate_with_multiplier("3/10seconds") == (3, 10)
    assert parse_rate_with_multiplier("10/minute") == (10, 60)
    assert parse_rate_with_multiplier("5/hour") == (5, 3600)
    with pytest.raises(ValueError):
        parse_rate_with_multiplier("ten per minute")


def test_submit_throttle_uses_plan_scope(make_user, rf):
    free, pro = make_user(), make_user(plan="PRO")
    throttle = SubmitThrottle()
    req = rf.post("/")
    req.user = free
    assert throttle.select_scope(req) == "submit_free"
    req.user = pro
    assert throttle.select_scope(req) == "submit_pro"
    assert BurstThrottle().num_requests == 3 and BurstThrottle().duration == 10


def test_submit_throttle_enforced(make_user, auth_client, problem_factory, monkeypatch):
    from django.core.cache import cache

    cache.clear()
    monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, "submit_free", "2/minute")
    client, problem = auth_client(make_user()), problem_factory()
    body = {"problem_slug": problem.slug, "language": "python", "code": "x=1"}
    codes = [client.post("/api/submissions/", body, format="json").status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_judge_callbacks_are_not_throttled(queued, auth_client, monkeypatch):
    from django.core.cache import cache

    cache.clear()
    monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, "anon", "1/hour")
    client = auth_client()
    assert client.get("/api/problems/").status_code == 200
    assert client.get("/api/problems/").status_code == 429  # anon throttle is active
    codes = [_callback(client, queued, {"status": "RUNNING"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 200]


# ─── WebSocket ────────────────────────────────────────────────────────────────

def _ws_scenario(path, cookie=None, origin=b"http://localhost:3000", expect=1):
    """Connect and read exactly `expect` server events (or until a close).
    asgiref cancels the application when receive_output() times out, so the
    helper never waits for "no more messages".
    Returns (connected, json_messages, close_event_or_None)."""
    from channels.testing import WebsocketCommunicator

    from config.asgi import application

    async def run():
        headers = [(b"origin", origin)] if origin else []
        if cookie:
            headers.append((b"cookie", cookie.encode()))
        comm = WebsocketCommunicator(application, path, headers=headers)
        connected, _ = await comm.connect(timeout=5)
        events = []
        if connected:
            while len(events) < expect:
                events.append(await comm.receive_output(timeout=5))
                if events[-1]["type"] == "websocket.close":
                    break
            if not events or events[-1]["type"] != "websocket.close":
                await comm.disconnect()
        messages = [json.loads(e["text"]) for e in events if e["type"] == "websocket.send"]
        closed = next((e for e in events if e["type"] == "websocket.close"), None)
        return connected, messages, closed

    return async_to_sync(run)()


def _cookie_for(user):
    from rest_framework_simplejwt.tokens import RefreshToken

    return f"{settings.SIMPLE_JWT['AUTH_COOKIE']}={RefreshToken.for_user(user).access_token}"


@pytest.mark.django_db(transaction=True)
def test_ws_owner_receives_snapshot(make_user, problem_factory):
    user, problem = make_user(), problem_factory()
    sub = Submission.objects.create(user=user, problem=problem, language="python", code="x", status="RUNNING")
    connected, messages, closed = _ws_scenario(f"/ws/submissions/{sub.id}/", cookie=_cookie_for(user), expect=2)
    assert connected and closed is None
    assert messages[0] == {"type": "connected", "submission_id": str(sub.id)}
    assert messages[1]["type"] == "status_update" and messages[1]["status"] == "RUNNING"


@pytest.mark.django_db(transaction=True)
def test_ws_rejects_anonymous_and_other_users(make_user, problem_factory):
    owner, stranger, problem = make_user(), make_user(), problem_factory()
    sub = Submission.objects.create(user=owner, problem=problem, language="python", code="x")
    _, msgs, closed = _ws_scenario(f"/ws/submissions/{sub.id}/")
    assert msgs == [] and closed is not None and closed["code"] == 4401
    _, msgs, closed = _ws_scenario(f"/ws/submissions/{sub.id}/", cookie=_cookie_for(stranger))
    assert msgs == [] and closed is not None and closed["code"] == 4403


@pytest.mark.django_db(transaction=True)
def test_ws_rejects_foreign_origin(make_user, problem_factory):
    user, problem = make_user(), problem_factory()
    sub = Submission.objects.create(user=user, problem=problem, language="python", code="x")
    connected, _, _ = _ws_scenario(f"/ws/submissions/{sub.id}/", cookie=_cookie_for(user), origin=b"https://evil.example")
    assert not connected
