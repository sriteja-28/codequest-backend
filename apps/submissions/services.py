"""
Submission lifecycle: judge callbacks, finalisation side effects, reaping.

State machine (enforced in apply_judge_callback):

    QUEUED ──RUNNING──▶ RUNNING ──terminal──▶ ACCEPTED | WRONG_ANSWER | ...
       └────────────terminal────────────────▶ (judge may skip RUNNING)

  * RUNNING is only applied to QUEUED submissions (late/duplicate RUNNING
    callbacks after a verdict are ignored).
  * The first terminal callback wins. Later terminal callbacks are duplicates
    (worker retry, RabbitMQ redelivery) and are acknowledged without effect —
    except that a real verdict may replace an INTERNAL_ERROR written by the
    stale-submission reaper.
  * Side effects (problem counters, solved records, streaks, contest scoring)
    run exactly once, inside the same transaction as the terminal transition.
"""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import Submission, SubmissionResult

logger = logging.getLogger(__name__)

S = Submission.Status
ACTIVE_STATUSES = frozenset({S.QUEUED, S.RUNNING})
TERMINAL_STATUSES = frozenset({
    S.ACCEPTED, S.WRONG_ANSWER, S.RUNTIME_ERROR, S.TIME_LIMIT,
    S.MEMORY_LIMIT, S.COMPILE_ERROR, S.INTERNAL_ERROR,
})

REAPED_MESSAGE = (
    "Judging did not complete in time (the judge job was lost or the worker crashed). "
    "Please submit again."
)

MAX_OUTPUT_CHARS = 65_536
MAX_ERROR_CHARS = 10_000


class InvalidCallback(Exception):
    """Callback payload is inconsistent with the submission (-> HTTP 400)."""


# ─── Broadcasting ─────────────────────────────────────────────────────────────

def submission_snapshot(submission) -> dict:
    return {
        "submission_id": str(submission.id),
        "status": submission.status,
        "runtime_ms": submission.runtime_ms,
        "memory_kb": submission.memory_kb,
    }


def broadcast_submission(snapshot: dict) -> None:
    """Push a status update to WebSocket subscribers (best effort)."""
    from apps.core.channels import send_to_group

    try:
        send_to_group(
            f"submission_{snapshot['submission_id']}",
            {"type": "submission_update", **snapshot},
        )
    except Exception as exc:  # broadcasting must never break persistence
        logger.warning("Could not broadcast submission update: %s", exc)


def _broadcast_after_commit(submission) -> None:
    snapshot = submission_snapshot(submission)
    transaction.on_commit(lambda: broadcast_submission(snapshot))


# ─── Judge callback ───────────────────────────────────────────────────────────

def _is_reaped(submission) -> bool:
    return submission.status == S.INTERNAL_ERROR and submission.error_message == REAPED_MESSAGE


def apply_judge_callback(submission_id, payload: dict) -> dict:
    """Apply a validated judge callback. Returns {"applied": bool, "status": str}.

    Raises Submission.DoesNotExist or InvalidCallback.
    """
    from apps.problems.models import TestCase

    new_status = payload["status"]
    now = timezone.now()

    with transaction.atomic():
        sub = Submission.objects.select_for_update().get(id=submission_id)

        if new_status == S.RUNNING:
            if sub.status != S.QUEUED:
                return {"applied": False, "status": sub.status}
            sub.status = S.RUNNING
            sub.judge_started_at = sub.judge_started_at or now
            sub.save(update_fields=["status", "judge_started_at"])
            _broadcast_after_commit(sub)
            return {"applied": True, "status": sub.status}

        if sub.status in TERMINAL_STATUSES and not _is_reaped(sub):
            logger.info("Ignoring duplicate terminal callback for %s (%s -> %s)", sub.id, sub.status, new_status)
            return {"applied": False, "status": sub.status}

        results = payload.get("results") or []
        tc_ids = {r["test_case_id"] for r in results}
        test_cases = {tc.id: tc for tc in TestCase.objects.filter(problem_id=sub.problem_id, id__in=tc_ids)}
        unknown = tc_ids - set(test_cases)
        if unknown:
            raise InvalidCallback(f"Test case(s) {sorted(unknown)} do not belong to this submission's problem.")

        sub.status = new_status
        sub.runtime_ms = payload.get("runtime_ms")
        sub.memory_kb = payload.get("memory_kb")
        sub.error_message = (payload.get("error_message") or "")[:MAX_ERROR_CHARS]
        sub.judge_started_at = sub.judge_started_at or now
        sub.judge_finished_at = now
        sub.save(update_fields=[
            "status", "runtime_ms", "memory_kb", "error_message",
            "judge_started_at", "judge_finished_at",
        ])

        SubmissionResult.objects.filter(submission=sub).delete()
        SubmissionResult.objects.bulk_create([
            SubmissionResult(
                submission=sub,
                test_case=test_cases[r["test_case_id"]],
                status=r["status"],
                actual_output=(r.get("actual_output") or "")[:MAX_OUTPUT_CHARS],
                expected_output=test_cases[r["test_case_id"]].expected_output,
                error_output=(r.get("error_output") or "")[:MAX_ERROR_CHARS],
                time_ms=r.get("time_ms"),
                memory_kb=r.get("memory_kb"),
            )
            for r in results
        ])

        finalize_submission(sub)
        _broadcast_after_commit(sub)
        return {"applied": True, "status": sub.status}


# ─── Side effects of a verdict (run once per submission) ─────────────────────

def finalize_submission(sub) -> None:
    """Counters, solved tracking, streaks and contest scoring for a newly
    terminal submission. Must be called inside the transaction that wrote the
    verdict. Sample runs ("Run" button) have no side effects."""
    from apps.problems.models import Problem
    from apps.users.models import User, UserDailyActivity, UserSolvedProblem
    from apps.users.progress import invalidate_progress

    if sub.is_sample_run or sub.status not in TERMINAL_STATUSES:
        return

    # Judge failures are not the user's attempt: they don't count.
    if sub.status != S.INTERNAL_ERROR:
        counters = {"total_submissions": F("total_submissions") + 1}
        if sub.status == S.ACCEPTED:
            counters["accepted_submissions"] = F("accepted_submissions") + 1
        Problem.objects.filter(pk=sub.problem_id).update(**counters)

        # Heatmap counters. A conditional UPDATE avoids a read-modify-write race
        # when two verdicts land at the same time.
        today = timezone.now().date()
        activity, _ = UserDailyActivity.objects.get_or_create(
            user_id=sub.user_id, date=today
        )
        fields = {"submissions": F("submissions") + 1}
        if sub.status == S.ACCEPTED:
            fields["accepted"] = F("accepted") + 1
        UserDailyActivity.objects.filter(pk=activity.pk).update(**fields)

        # The progress payload is cached; refresh it once this transaction commits.
        user_id = sub.user_id
        transaction.on_commit(lambda: invalidate_progress(user_id))

    if sub.status == S.ACCEPTED:
        solved, created = UserSolvedProblem.objects.get_or_create(
            user_id=sub.user_id,
            problem_id=sub.problem_id,
            defaults={"best_runtime_ms": sub.runtime_ms, "best_memory_kb": sub.memory_kb},
        )
        if not created:
            changed = []
            if sub.runtime_ms is not None and (solved.best_runtime_ms is None or sub.runtime_ms < solved.best_runtime_ms):
                solved.best_runtime_ms = sub.runtime_ms
                changed.append("best_runtime_ms")
            if sub.memory_kb is not None and (solved.best_memory_kb is None or sub.memory_kb < solved.best_memory_kb):
                solved.best_memory_kb = sub.memory_kb
                changed.append("best_memory_kb")
            if changed:
                solved.save(update_fields=changed)

        user = User.objects.select_for_update().get(pk=sub.user_id)
        user.problems_solved = UserSolvedProblem.objects.filter(user_id=user.pk).count()
        user.save(update_fields=["problems_solved"])
        # Streak = consecutive UTC days with an accepted submission
        # (same definition as `manage.py recalculate_streaks`).
        user.update_streak()

    if sub.contest_id:
        from apps.contests.scoring import handle_contest_submission
        from apps.contests.views import _broadcast_leaderboard

        if handle_contest_submission(sub):
            slug = sub.contest.slug
            transaction.on_commit(lambda: _broadcast_leaderboard(slug))


# ─── Stale submissions ────────────────────────────────────────────────────────

def stale_cutoff(now=None, max_age_seconds=None):
    now = now or timezone.now()
    return now - timedelta(seconds=max_age_seconds or settings.JUDGE_STALE_SUBMISSION_SECONDS)


def _stale_filter(cutoff) -> Q:
    return (
        Q(status=S.QUEUED, created_at__lt=cutoff)
        | Q(status=S.RUNNING, judge_started_at__lt=cutoff)
        | Q(status=S.RUNNING, judge_started_at__isnull=True, created_at__lt=cutoff)
    )


def reap_stale_submissions(max_age_seconds=None, submission_ids=None, limit=1000) -> int:
    """Mark submissions stuck in QUEUED/RUNNING as INTERNAL_ERROR. A verdict
    that arrives later still replaces the reaped state (see apply_judge_callback)."""
    cutoff = stale_cutoff(max_age_seconds=max_age_seconds)
    qs = Submission.objects.filter(_stale_filter(cutoff))
    if submission_ids is not None:
        qs = qs.filter(id__in=submission_ids)
    reaped = 0
    for sid in list(qs.values_list("id", flat=True)[:limit]):
        with transaction.atomic():
            sub = Submission.objects.select_for_update().get(id=sid)
            if not Submission.objects.filter(_stale_filter(cutoff), id=sid).exists():
                continue
            sub.status = S.INTERNAL_ERROR
            sub.error_message = REAPED_MESSAGE
            sub.judge_finished_at = timezone.now()
            sub.save(update_fields=["status", "error_message", "judge_finished_at"])
            _broadcast_after_commit(sub)
            reaped += 1
    if reaped:
        logger.warning("Reaped %d stale submission(s) older than %s", reaped, cutoff.isoformat())
    return reaped


# ─── Public (non-admin) view of error output ─────────────────────────────────

_EXC_NAME_RE = re.compile(r"\b([A-Za-z_][\w.$]*(?:Error|Exception))\b")


def public_error_message(submission, results) -> str:
    """Error text safe to show the submitting user.

    Compile errors are test-independent and shown in full. Runtime failures on
    a hidden test case could echo the hidden input (e.g. a program printing its
    stdin to stderr), so only the exception class name is revealed.
    """
    message = submission.error_message or ""
    if not message or submission.status == S.COMPILE_ERROR or message == REAPED_MESSAGE:
        return message
    first_failed = next((r for r in results if r.status != S.ACCEPTED), None)
    if first_failed is None or not first_failed.test_case.is_hidden:
        return message
    names = _EXC_NAME_RE.findall(message)
    detail = f" ({names[-1]})" if names else ""
    label = S(submission.status).label if submission.status in S.values else submission.status
    return f"{label} on a hidden test case{detail}. Output of hidden test cases is not shown."
