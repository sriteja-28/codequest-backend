from django.core.management.base import BaseCommand
from apps.users.models import User, UserSolvedProblem


class Command(BaseCommand):
    help = "Recalculate problems_solved count for all users from UserSolvedProblem table"

    def handle(self, *args, **options):
        users = User.objects.all()
        updated = 0

        for user in users:
            actual_count = UserSolvedProblem.objects.filter(user=user).count()
            
            if user.problems_solved != actual_count:
                self.stdout.write(
                    f"  {user.username}: {user.problems_solved} → {actual_count}"
                )
                user.problems_solved = actual_count
                user.save(update_fields=["problems_solved"])
                updated += 1
            else:
                self.stdout.write(f"  {user.username}: {actual_count} ✓ (correct)")

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Fixed {updated} users")
        )