"""Report email collisions that the OAuth rollout should resolve before launch.

Two kinds are reported:

  1. users whose emails differ only by case (the users table treats them as
     distinct, the sign-in lookup uses iexact);
  2. linked social identities whose provider email belongs to a different
     CodeQuest account (informational: it is not auto-merged by design).

    python manage.py report_duplicate_emails
    python manage.py report_duplicate_emails --fail   # non-zero exit if any
"""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from apps.users.models import SocialIdentity, User


class Command(BaseCommand):
    help = "List case-variant duplicate emails and identities pointing at another account's email."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail",
            action="store_true",
            help="Exit with an error when anything is reported (for CI/pre-deploy checks).",
        )

    def handle(self, *args, **options):
        by_email = defaultdict(list)
        for user in User.objects.order_by("id").values("id", "email", "username"):
            by_email[user["email"].strip().lower()].append(user)

        duplicates = {email: users for email, users in by_email.items() if len(users) > 1}
        for email, users in sorted(duplicates.items()):
            listing = ", ".join(f"#{u['id']} {u['username']}" for u in users)
            self.stdout.write(self.style.WARNING(f"duplicate email {email}: {listing}"))

        mismatches = []
        identities = SocialIdentity.objects.exclude(email="").select_related("user")
        for identity in identities:
            owners = by_email.get(identity.email.strip().lower(), [])
            others = [u for u in owners if u["id"] != identity.user_id]
            if others:
                mismatches.append((identity, others))

        for identity, others in mismatches:
            listing = ", ".join(f"#{u['id']} {u['username']}" for u in others)
            self.stdout.write(
                f"identity {identity.provider} for #{identity.user_id} {identity.user.username} "
                f"uses email {identity.email}, also used by {listing}"
            )

        self.stdout.write(
            f"Checked {User.objects.count()} users and {SocialIdentity.objects.count()} identities: "
            f"{len(duplicates)} case-variant duplicate email(s), {len(mismatches)} cross-account identity email(s)."
        )
        if options["fail"] and (duplicates or mismatches):
            raise CommandError("Email collisions reported.")
