"""Finalize ended contests: freeze the final standings and release their problems.

Safe to run as often as you like (e.g. every 5 minutes from cron or a scheduler);
contests are also finalized lazily by the first API request that touches them.
See apps/contests/finalize.py.

    python manage.py finalize_contests              # every due contest
    python manage.py finalize_contests --dry-run    # list what is due
    python manage.py finalize_contests --slug weekly-12 --force
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contests.finalize import FINALIZED, due_contests, finalize_contest, pending_submissions
from apps.contests.models import Contest


class Command(BaseCommand):
    help = "Finalize ended contests: freeze the final standings and release their problems to practice."

    def add_arguments(self, parser):
        parser.add_argument("--slug", help="Only this contest.")
        parser.add_argument("--dry-run", action="store_true", help="List the due contests without changing anything.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Do not wait for submissions that are still being judged (they will not count).",
        )

    def handle(self, *args, slug=None, dry_run=False, force=False, **options):
        if slug:
            contest = Contest.objects.filter(slug=slug).first()
            if contest is None:
                raise CommandError(f"No contest with slug {slug!r}.")
            if contest.finalized_at:
                self.stdout.write(f"{slug}: already finalized at {contest.finalized_at.isoformat()}")
                return
            if timezone.now() <= contest.end_at:
                raise CommandError(f"{slug} has not ended yet (ends {contest.end_at.isoformat()}).")
            contests = [contest]
        else:
            contests = list(due_contests())

        if not contests:
            self.stdout.write("No contests to finalize.")
            return

        if dry_run:
            for contest in contests:
                pending = pending_submissions(contest).count()
                note = f", {pending} submission(s) still judging" if pending else ""
                self.stdout.write(f"due: {contest.slug} (ended {contest.end_at.isoformat()}{note})")
            self.stdout.write(f"{len(contests)} contest(s) due (dry run, nothing changed).")
            return

        finalized = 0
        for contest in contests:
            result = finalize_contest(contest, force=force)
            if result.outcome == FINALIZED:
                finalized += 1
                self.stdout.write(self.style.SUCCESS(
                    f"finalized: {contest.slug} ({result.participants} participant(s), "
                    f"{result.released} problem(s) released)"
                ))
            else:
                extra = f", {result.pending} submission(s) still judging" if result.pending else ""
                self.stdout.write(f"skipped: {contest.slug} ({result.outcome}{extra})")
        self.stdout.write(f"{finalized} of {len(contests)} contest(s) finalized.")
