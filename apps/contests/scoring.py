"""
Contest scoring (ICPC-style).

* A problem's score is awarded on the participant's first ACCEPTED submission.
* WRONG_ANSWER / RUNTIME_ERROR / TIME_LIMIT / MEMORY_LIMIT before the first
  accept count as wrong attempts; COMPILE_ERROR and INTERNAL_ERROR are free.
* Only submissions *created* inside [start_at, end_at] by a registered,
  non-disqualified participant count (submission creation also rejects
  out-of-window submissions; this is defence in depth for late verdicts).
* Ranking: score desc, then penalty asc (sum over solved problems of
  solve_time_minutes + WRONG_ANSWER_PENALTY_MINUTES * wrong_attempts), then
  earliest last accept, then registration time.

handle_contest_submission() is called exactly once per submission from
apps.submissions.services.finalize_submission (inside its transaction).
Verdicts for one contest are applied one at a time (contest row lock): every
verdict re-ranks all participants, and without the lock two verdicts could
deadlock on each other's participant rows. Once the contest is finalized
(apps/contests/finalize.py) verdicts no longer change the standings.
"""

from django.db import transaction
from django.db.models import Sum

from .models import Contest, ContestParticipant, ContestProblem, ContestSubmissionStat

WRONG_ANSWER_PENALTY_MINUTES = 10  # Like ICPC/Codeforces
PENALIZED_STATUSES = {"WRONG_ANSWER", "RUNTIME_ERROR", "TIME_LIMIT", "MEMORY_LIMIT"}


def handle_contest_submission(submission) -> bool:
    """Update the participant's stats for a judged contest submission.
    Returns True when standings may have changed."""
    if not submission.contest_id or submission.is_sample_run:
        return False
    if submission.status == "INTERNAL_ERROR":
        return False

    from apps.submissions.models import Submission

    with transaction.atomic():
        # Lock order problem -> contest -> participants (the problem row is
        # already locked by the counter update in finalize_submission).
        contest = Contest.objects.select_for_update().get(pk=submission.contest_id)
        if contest.finalized_at:
            return False
        created = submission.created_at
        if created < contest.start_at or (contest.end_at and created > contest.end_at):
            return False
        try:
            contest_problem = ContestProblem.objects.get(contest_id=contest.pk, problem_id=submission.problem_id)
            participant = ContestParticipant.objects.select_for_update().get(
                contest_id=contest.pk, user_id=submission.user_id
            )
        except (ContestProblem.DoesNotExist, ContestParticipant.DoesNotExist):
            return False
        if participant.is_disqualified:
            return False

        stat, _ = ContestSubmissionStat.objects.get_or_create(
            participant=participant, contest_problem=contest_problem
        )
        # Workers can finish out of order. Rebuild this problem's small aggregate
        # by submission time, so late earlier accepts/wrong answers stay fair.
        attempts = Submission.objects.filter(
            contest=contest, user_id=submission.user_id, problem_id=submission.problem_id,
            is_sample_run=False, created_at__gte=contest.start_at, created_at__lte=contest.end_at,
        )
        first_accept = attempts.filter(status="ACCEPTED").order_by("created_at", "id").first()
        wrong = attempts.filter(status__in=PENALIZED_STATUSES)
        if first_accept:
            wrong = wrong.filter(created_at__lt=first_accept.created_at)
        stat.wrong_attempts = wrong.count()
        stat.is_solved = first_accept is not None
        stat.first_solved_at = first_accept.created_at if first_accept else None
        stat.solve_time_minutes = (
            int((first_accept.created_at - contest.start_at).total_seconds() // 60) if first_accept else None
        )
        stat.score_awarded = contest_problem.score if first_accept else 0
        stat.save()
        recalculate_score(participant)

        recalculate_ranks(contest)
    return True


def recalculate_score(participant):
    """final_score = points of solved problems + the admin's score_adjustment."""
    total = ContestSubmissionStat.objects.filter(
        participant=participant, is_solved=True
    ).aggregate(total=Sum("score_awarded"))["total"] or 0
    participant.final_score = total + participant.score_adjustment
    participant.save(update_fields=["final_score"])


def participant_penalty_minutes(participant) -> int:
    penalty = 0
    for stat in participant.problem_stats.all():
        if stat.is_solved:
            penalty += (stat.solve_time_minutes or 0) + WRONG_ANSWER_PENALTY_MINUTES * stat.wrong_attempts
    return penalty


def recalculate_ranks(contest):
    """Rank every non-disqualified participant (ties broken as in the module docstring)."""
    participants = list(
        ContestParticipant.objects.filter(contest=contest, is_disqualified=False)
        .prefetch_related("problem_stats")
    )

    def sort_key(p):
        solved_times = [s.first_solved_at for s in p.problem_stats.all() if s.is_solved and s.first_solved_at]
        last_solve = max(solved_times) if solved_times else None
        return (
            -p.final_score,
            participant_penalty_minutes(p),
            last_solve is None,
            last_solve or p.registered_at,
            p.registered_at,
            p.pk,
        )

    participants.sort(key=sort_key)
    for i, p in enumerate(participants):
        if p.rank != i + 1:
            p.rank = i + 1
            p.save(update_fields=["rank"])
