"""Contest finalization: freeze the final standings and release the problems.

A contest is *due* once it has ended. It is finalized as soon as every
submission made inside its window has a verdict, or once the judging grace
period after the end has passed (CONTEST_FINALIZE_GRACE_SECONDS); verdicts that
arrive after finalization no longer change the standings.

Finalizing a contest:
  1. recomputes the ranking with the live scoring rules (apps/contests/scoring.py)
     and clears the rank of disqualified participants;
  2. publishes the unpublished problems it owes the practice catalogue: a problem
     is owed once a finalized *public* contest with `release_problems` contains it,
     and it is held back while an unfinished (upcoming/live) round still uses it;
     that round's own finalization releases it later, even when that round is
     private or does not release problems itself;
  3. stamps `finalized_at`; scoring ignores every later verdict;
  4. records an AdminLog entry (system action, no admin) and pushes the final board.

Entry points: `manage.py finalize_contests` (cron), the Django admin action, and,
lazily, the first API request that touches an ended contest, so a missed cron
run never leaves a contest open. Finalizing is idempotent. Finalized standings
are read-only; a fresh contest is needed for another round.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Contest, ContestParticipant, ContestProblem

logger = logging.getLogger(__name__)

FINALIZED = "finalized"
ALREADY = "already_finalized"
NOT_ENDED = "not_ended"
PENDING = "judging_pending"

# Request paths finalize at most this many overdue contests per call.
LAZY_LIMIT = 10


@dataclass
class FinalizeResult:
    contest: Contest
    outcome: str
    released: int = 0
    pending: int = 0
    participants: int = 0


def grace_period() -> timedelta:
    return timedelta(seconds=settings.CONTEST_FINALIZE_GRACE_SECONDS)


def due_contests(now=None):
    """Ended contests that have not been finalized yet, oldest end first."""
    now = now or timezone.now()
    return Contest.objects.filter(finalized_at__isnull=True, end_at__lt=now).order_by("end_at", "id")


def pending_submissions(contest):
    """Contest submissions made inside the window that are still waiting for a verdict."""
    from apps.submissions.models import Submission
    from apps.submissions.services import ACTIVE_STATUSES, REAPED_MESSAGE

    return Submission.objects.filter(
        Q(status__in=ACTIVE_STATUSES)
        | Q(status=Submission.Status.INTERNAL_ERROR, error_message=REAPED_MESSAGE),
        contest=contest,
        is_sample_run=False,
        created_at__gte=contest.start_at,
        created_at__lte=contest.end_at,
    )


def _release_owed_problems(problem_ids, now) -> int:
    """Publish the unpublished problems among `problem_ids` that are owed to practice
    (rule in the module docstring). The caller holds the problem row locks."""
    from apps.problems.models import Problem

    if not problem_ids:
        return 0
    owed = ContestProblem.objects.filter(
        problem_id__in=problem_ids,
        contest__is_public=True,
        contest__release_problems=True,
        contest__finalized_at__isnull=False,
    ).values("problem_id")
    reserved = ContestProblem.objects.filter(
        problem_id__in=problem_ids,
        contest__finalized_at__isnull=True,
        contest__end_at__gte=now,
    ).values("problem_id")
    return (
        Problem.objects.filter(pk__in=owed, is_published=False)
        .exclude(pk__in=reserved)
        .update(is_published=True)
    )


def finalize_contest(contest, *, now=None, force=False, actor=None, source=None) -> FinalizeResult:
    """Finalize one contest (see the module docstring). `force` skips waiting for
    judging; `actor`/`source` describe who asked (audit), None for system runs."""
    from apps.admin_panel.audit import record
    from apps.problems.models import Problem

    from .scoring import recalculate_ranks
    from .views import _broadcast_leaderboard

    now = now or timezone.now()
    if contest.finalized_at:
        return FinalizeResult(contest, ALREADY)
    if now <= contest.end_at:
        return FinalizeResult(contest, NOT_ENDED)
    # Lock-free early exit while judging is still running: request paths call
    # this often right after a contest ends, and verdicts need the same rows.
    # The decision is re-checked under the locks below.
    if not force and now < contest.end_at + grace_period():
        pending = pending_submissions(contest).count()
        if pending:
            return FinalizeResult(contest, PENDING, pending=pending)

    with transaction.atomic():
        problem_ids = list(
            ContestProblem.objects.filter(contest_id=contest.pk).values_list("problem_id", flat=True)
        )
        # Verdict processing locks problem -> contest -> participants; take the
        # same order so a late verdict can never deadlock with finalization.
        list(Problem.objects.select_for_update().filter(pk__in=problem_ids).order_by("pk").only("pk"))
        locked = Contest.objects.select_for_update().get(pk=contest.pk)
        if locked.finalized_at:
            contest.finalized_at = locked.finalized_at
            return FinalizeResult(contest, ALREADY)
        # The schedule may have changed while this caller waited for the lock.
        if now <= locked.end_at:
            return FinalizeResult(locked, NOT_ENDED)

        pending = pending_submissions(locked).count()
        if pending and not force and now < locked.end_at + grace_period():
            return FinalizeResult(contest, PENDING, pending=pending)

        recalculate_ranks(locked)
        ContestParticipant.objects.filter(contest=locked, is_disqualified=True).exclude(rank=None).update(rank=None)
        participants = ContestParticipant.objects.filter(contest=locked).count()

        locked.finalized_at = now
        locked.save(update_fields=["finalized_at", "updated_at"])
        # After the stamp, so this contest counts as a finalized releasing round.
        released = _release_owed_problems(problem_ids, now)

        note = f" {pending} submission(s) were still being judged and do not count." if pending else ""
        record(
            actor=actor,
            source=source,
            action="UPDATE",
            obj=locked,
            changes={"finalized_at": [None, now.isoformat()]},
            description=(
                f"Finalized contest '{locked.slug}': final standings frozen for {participants} "
                f"participant(s); {released} problem(s) released to practice.{note}"
            ),
        )
        slug = locked.slug
        transaction.on_commit(lambda: _broadcast_leaderboard(slug))

    contest.finalized_at = now
    logger.info("Finalized contest %s (%d participants, %d problems released)", contest.slug, participants, released)
    return FinalizeResult(contest, FINALIZED, released=released, pending=pending, participants=participants)


def finalize_due_contests(*, now=None, limit=None, force=False):
    """Finalize every due contest (or the first `limit`); returns the results."""
    qs = due_contests(now)
    if limit:
        qs = qs[:limit]
    return [finalize_contest(contest, now=now, force=force) for contest in list(qs)]


def maybe_finalize(contest):
    """Lazy finalization on request paths: never raises, never blocks the response on errors."""
    if contest.finalized_at or timezone.now() <= contest.end_at:
        return None
    try:
        return finalize_contest(contest)
    except Exception:  # noqa: BLE001 - finalization is retried on the next request / cron run
        logger.exception("Lazy finalization of contest %s failed", contest.slug)
        return None


def finalize_due_lazily():
    """Called by list endpoints: bounded, and never raises."""
    try:
        return finalize_due_contests(limit=LAZY_LIMIT)
    except Exception:  # noqa: BLE001
        logger.exception("Lazy finalization of due contests failed")
        return []
