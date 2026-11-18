"""Grant or change a platform role, keeping Django admin access in sync.

    python manage.py grant_role person@example.com ADMIN
    python manage.py grant_role person@example.com MODERATOR
    python manage.py grant_role person@example.com ADMIN --superuser
    python manage.py grant_role person@example.com USER --no-staff

ADMIN also sets is_staff (Django admin access). Demoting away from ADMIN
removes is_staff unless the account is a superuser or --no-staff was given.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.admin_panel.audit import record
from apps.users.models import User

ROLES = [choice for choice, _label in User.Role.choices]


class Command(BaseCommand):
    help = "Grant or change a user's role: USER, MODERATOR or ADMIN."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Account email (case-insensitive).")
        parser.add_argument("role", choices=ROLES, type=str.upper, help="New role.")
        parser.add_argument("--superuser", action="store_true", help="Also grant Django superuser.")
        parser.add_argument("--no-staff", action="store_true", help="Never change is_staff.")

    def handle(self, *args, **options):
        email = options["email"]
        role = options["role"]
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f"No user with email {email!r}.")

        old_role = user.role
        user.role = role
        if not options["no_staff"]:
            if role == User.Role.ADMIN or options["superuser"]:
                user.is_staff = True
            elif not user.is_superuser:
                user.is_staff = False
        if options["superuser"]:
            if role != User.Role.ADMIN:
                raise CommandError("--superuser requires the ADMIN role.")
            user.is_superuser = True

        user.save(update_fields=["role", "is_staff", "is_superuser"])
        record(
            action="UPDATE",
            obj=user,
            description=(
                f"grant_role: {old_role} -> {role}; is_staff={user.is_staff}; "
                f"is_superuser={user.is_superuser}"
            ),
            source="system",
        )
        self.stdout.write(self.style.SUCCESS(
            f"{user.email}: role {old_role} -> {role}, "
            f"is_staff={user.is_staff}, is_superuser={user.is_superuser}"
        ))
