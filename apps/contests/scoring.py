from django.utils import timezone
from .models import ContestParticipant, ContestProblem, ContestSubmissionStat

WRONG_ANSWER_PENALTY_MINUTES = 10  # Like Codeforces


def handle_contest_submission(submission):
    """
    Called after a submission is judged.
    Updates ContestSubmissionStat and recalculates participant score/rank.
    """
    if not submission.contest_id:
        return

    try:
        contest_problem = ContestProblem.objects.get(
            contest_id=submission.contest_id,
            problem_id=submission.problem_id,
        )
        participant = ContestParticipant.objects.get(
            contest_id=submission.contest_id,
            user_id=submission.user_id,
        )
    except (ContestProblem.DoesNotExist, ContestParticipant.DoesNotExist):
        return

    stat, _ = ContestSubmissionStat.objects.get_or_create(
        participant=participant,
        contest_problem=contest_problem,
    )

    # Already solved — don't update
    if stat.is_solved:
        return

    if submission.status == "ACCEPTED":
        contest_start = contest_problem.contest.start_at
        solve_time = int((timezone.now() - contest_start).total_seconds() / 60)
        penalty = stat.wrong_attempts * WRONG_ANSWER_PENALTY_MINUTES

        stat.is_solved = True
        stat.solve_time_minutes = solve_time
        stat.first_solved_at = timezone.now()
        # Score = full points (you can add time-based decay here)
        stat.score_awarded = contest_problem.score
        stat.save()

        # Recalculate total score for participant
        _recalculate_score(participant)

    elif submission.status in ["WRONG_ANSWER", "RUNTIME_ERROR", "TIME_LIMIT", "MEMORY_LIMIT"]:
        stat.wrong_attempts += 1
        stat.save()

    # Recalculate ranks for all participants
    _recalculate_ranks(contest_problem.contest)


def _recalculate_score(participant):
    from django.db.models import Sum
    total = ContestSubmissionStat.objects.filter(
        participant=participant, is_solved=True
    ).aggregate(total=Sum("score_awarded"))["total"] or 0
    participant.final_score = total
    participant.save(update_fields=["final_score"])


def _recalculate_ranks(contest):
    """Rank all participants by score desc, then by earliest last solve time."""
    participants = list(
        ContestParticipant.objects.filter(
            contest=contest, is_disqualified=False
        ).prefetch_related("problem_stats")
    )

    def sort_key(p):
        last_solve = ContestSubmissionStat.objects.filter(
            participant=p, is_solved=True
        ).order_by("-first_solved_at").values_list("first_solved_at", flat=True).first()
        return (-p.final_score, last_solve or timezone.now())

    participants.sort(key=sort_key)
    for i, p in enumerate(participants):
        p.rank = i + 1
        p.save(update_fields=["rank"])