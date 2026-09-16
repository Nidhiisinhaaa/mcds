from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "Create a doctor account (doctors cannot self-register via the API)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--name", required=True, help="Doctor's full name")
        parser.add_argument("--email", required=False, default="")

    def handle(self, *args, **options):
        username = options["username"]
        if User.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists")

        names = options["name"].strip().split(" ", 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""

        user = User(
            username=username,
            email=options["email"],
            role=User.Role.DOCTOR,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_password(options["password"])
        user.save()

        self.stdout.write(
            self.style.SUCCESS(f"Doctor account '{username}' created (id={user.id}).")
        )
