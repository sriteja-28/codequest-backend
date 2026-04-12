from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Submission

TERMINAL_STATUSES = {"ACCEPTED", "WRONG_ANSWER", "RUNTIME_ERROR", "TIME_LIMIT", "MEMORY_LIMIT", "COMPILE_ERROR", "INTERNAL_ERROR"}

@receiver(post_save, sender=Submission)
def on_submission_saved(sender, instance, **kwargs):
    """
    Fires every time a Submission is saved.
    Only acts when status reaches a terminal state AND submission belongs to a contest.
    """
    if instance.status not in TERMINAL_STATUSES:
        return
    if not instance.contest_id:
        return

    # Update contest scoring
    from apps.contests.scoring import handle_contest_submission
    handle_contest_submission(instance)

    # Broadcast updated leaderboard via WebSocket
    from apps.contests.views import _broadcast_leaderboard
    _broadcast_leaderboard(instance.contest.slug)