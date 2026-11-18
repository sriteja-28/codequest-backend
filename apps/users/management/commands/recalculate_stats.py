from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from apps.users.models import User, UserSolvedProblem


class Command(BaseCommand):
    help = (
        "Recalculate denormalised counters from source data: each user's problems_solved "
        "(UserSolvedProblem rows) and each problem's total/accepted submission counts "
        "(judged, non-sample submissions excluding INTERNAL_ERROR)."
    )

    def handle(self, *args, **options):
        updated_users = 0
        for user in User.objects.all():
            actual = UserSolvedProblem.objects.filter(user=user).count()
            if user.problems_solved != actual:
                self.stdout.write(f"  user {user.username}: problems_solved {user.problems_solved} -> {actual}")
                user.problems_solved = actual
                user.save(update_fields=["problems_solved"])
                updated_users += 1

        from apps.problems.models import Problem

        counted = Q(submissions__is_sample_run=False) & ~Q(submissions__status__in=["QUEUED", "RUNNING", "INTERNAL_ERROR"])
        updated_problems = 0
        for problem in Problem.objects.annotate(
            n_total=Count("submissions", filter=counted),
            n_accepted=Count("submissions", filter=counted & Q(submissions__status="ACCEPTED")),
        ):
            if (problem.total_submissions, problem.accepted_submissions) != (problem.n_total, problem.n_accepted):
                self.stdout.write(
                    f"  problem {problem.slug}: total {problem.total_submissions} -> {problem.n_total}, "
                    f"accepted {problem.accepted_submissions} -> {problem.n_accepted}"
                )
                Problem.objects.filter(pk=problem.pk).update(
                    total_submissions=problem.n_total, accepted_submissions=problem.n_accepted
                )
                updated_problems += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nFixed {updated_users} user(s) and {updated_problems} problem(s)"
        ))
