from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db.models.functions import TruncDate

from apps.submissions.models import Submission
from apps.users.models import UserDailyActivity
from apps.users.progress import invalidate_progress


class Command(BaseCommand):
    help = (
        "Rebuild UserDailyActivity heatmap rows from judged submission history. "
        "Idempotent; run once after upgrading a database that predates the heatmap."
    )

    def handle(self, *args, **options):
        rows = (
            Submission.objects.filter(is_sample_run=False)
            .exclude(status__in=["QUEUED", "RUNNING", "INTERNAL_ERROR"])
            .annotate(day=TruncDate("created_at"))
            .values("user_id", "day")
            .annotate(
                submissions=Count("id"),
                accepted=Count("id", filter=Q(status=Submission.Status.ACCEPTED)),
            )
            .order_by("user_id", "day")
        )

        updated = 0
        user_ids = set()
        for row in rows.iterator():
            UserDailyActivity.objects.update_or_create(
                user_id=row["user_id"],
                date=row["day"],
                defaults={
                    "submissions": row["submissions"],
                    "accepted": row["accepted"],
                },
            )
            user_ids.add(row["user_id"])
            updated += 1

        for user_id in user_ids:
            invalidate_progress(user_id)

        self.stdout.write(self.style.SUCCESS(
            f"Rebuilt {updated} daily activity row(s) for {len(user_ids)} user(s)."
        ))
