"""Who may open a contest's problems, and when.

Contest problems are normally authored *unpublished*: they stay out of the
practice catalogue and are reached through their contest once it starts.
Finalization (apps/contests/finalize.py) later releases them to practice.

Rules (admins bypass the clock):

* before the start  nobody can open them (`contest_not_started`);
* while live        anyone may read them and run the samples, whatever their
                    plan or the problem's publish state; submitting for the
                    contest also needs a registration (submission_block_reason);
* after the end     still readable through the contest (archive view), but the
                    normal Pro gate applies again.
"""

from django.utils import timezone

from .models import Contest, ContestParticipant, ContestProblem


class ContestAccessError(Exception):
    NOT_STARTED = "contest_not_started"
    NOT_IN_CONTEST = "not_in_contest"
    PRO_REQUIRED = "pro_required"

    def __init__(self, code: str, message: str, problem=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.problem = problem


def _is_admin(user) -> bool:
    return bool(user and user.is_authenticated and getattr(user, "is_admin", False))


def visible_contest(*, user, pk=None, slug=None):
    """The contest when `user` may see it (public ones; admins see all), else None."""
    lookup = {"pk": pk} if pk is not None else {"slug": slug}
    contest = Contest.objects.filter(**lookup).first()
    if contest is None or (not contest.is_public and not _is_admin(user)):
        return None
    return contest


def contest_problem_for(contest, problem_slug: str, user):
    """The contest's problem `problem_slug` if `user` may open it now; else ContestAccessError."""
    from apps.problems.views import user_can_view_problem

    if contest.status == "upcoming" and not _is_admin(user):
        raise ContestAccessError(ContestAccessError.NOT_STARTED, "Problems are revealed when the contest starts.")
    link = (
        ContestProblem.objects.select_related("problem")
        .filter(contest=contest, problem__slug=problem_slug)
        .first()
    )
    if link is None:
        raise ContestAccessError(ContestAccessError.NOT_IN_CONTEST, "This problem is not part of the contest.")
    problem = link.problem
    if contest.status != "live" and not user_can_view_problem(user, problem):
        raise ContestAccessError(
            ContestAccessError.PRO_REQUIRED, "This problem is available on the Pro plan.", problem
        )
    return problem


def submission_block_reason(contest, user):
    """Why `user` may not submit for `contest` right now; None when allowed."""
    now = timezone.now()
    if contest.is_finalized:
        return "This contest has ended; submit outside the contest instead."
    if now < contest.start_at:
        return "This contest has not started yet."
    if contest.end_at and now > contest.end_at:
        return "This contest has ended; submit outside the contest instead."
    participant = ContestParticipant.objects.filter(contest=contest, user=user).first()
    if participant is None:
        return "Register for the contest before submitting."
    if participant.is_disqualified:
        return "You are disqualified from this contest."
    return None


def participations_by_contest(user) -> dict:
    """{contest_id: ContestParticipant} for the user (empty for visitors)."""
    if not user or not user.is_authenticated:
        return {}
    rows = ContestParticipant.objects.filter(user=user).only(
        "contest_id", "rank", "final_score", "is_disqualified"
    )
    return {row.contest_id: row for row in rows}
