from django.conf import settings
from django.core.management.base import BaseCommand

from apps.submissions.services import reap_stale_submissions


class Command(BaseCommand):
    help = (
        "Mark submissions stuck in QUEUED/RUNNING as INTERNAL_ERROR (lost judge job, "
        "crashed worker, failed callback). Safe to run periodically (cron / scheduler)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than",
            type=int,
            default=settings.JUDGE_STALE_SUBMISSION_SECONDS,
            help="Age in seconds after which an active submission is considered stuck "
                 "(default: JUDGE_STALE_SUBMISSION_SECONDS).",
        )

    def handle(self, *args, **options):
        count = reap_stale_submissions(max_age_seconds=options["older_than"])
        self.stdout.write(self.style.SUCCESS(f"Reaped {count} stuck submission(s)."))
