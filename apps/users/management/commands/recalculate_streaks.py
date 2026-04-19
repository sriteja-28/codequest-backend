# apps/users/management/commands/recalculate_streaks.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User, UserSolvedProblem
from apps.submissions.models import Submission


class Command(BaseCommand):
    help = "Recalculate current_streak and best_streak for all users from submission history"

    def handle(self, *args, **options):
        users = User.objects.all()
        updated = 0

        for user in users:
            # Get all accepted, non-sample submission dates for this user
            accepted_dates = sorted(set(
                Submission.objects.filter(
                    user=user,
                    status="ACCEPTED",
                    is_sample_run=False,
                )
                .values_list("created_at", flat=True)
                # Convert to date strings
            ))

            if not accepted_dates:
                continue

            # Convert datetimes to unique date strings sorted asc
            day_strings = sorted(set(
                dt.date().isoformat() for dt in accepted_dates
            ))

            from datetime import date, timedelta

            days = [date.fromisoformat(d) for d in day_strings]

            # Calculate best streak
            best = 1
            run = 1
            for i in range(1, len(days)):
                if days[i] - days[i - 1] == timedelta(days=1):
                    run += 1
                    if run > best:
                        best = run
                else:
                    run = 1

            # Calculate current streak (must end today or yesterday)
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            last_day = days[-1]

            if last_day < yesterday:
                # Gap — streak is broken
                current = 0
            else:
                # Walk backwards from the last solved day
                current = 1
                for i in range(len(days) - 1, 0, -1):
                    if days[i] - days[i - 1] == timedelta(days=1):
                        current += 1
                    else:
                        break

            user.best_streak = best
            user.current_streak = current
            user.last_active_date = last_day
            user.save(update_fields=["best_streak", "current_streak", "last_active_date"])

            self.stdout.write(
                f"  {user.username}: current={current}, best={best}, last={last_day}"
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"\n✅ Recalculated streaks for {updated} users"))