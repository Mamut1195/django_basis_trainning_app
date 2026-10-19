from django.core.management.base import BaseCommand, CommandError

from basis.bootstrap.accounts import identity
from basis.modules.accounts.public import LinkLegacyProfile
from basis.modules.athletes.public import InvalidAthleteData
from basis.shared.identifiers import AccountId, AthleteId


class Command(BaseCommand):
    help = "Explicit operator-only mapping; never guesses owners by IDs or emails."

    def add_arguments(self, parser):
        parser.add_argument("--account-id", type=int, required=True)
        parser.add_argument("--profile-id", type=int, required=True)

    def handle(self, *args, **options):
        try:
            identity().link_legacy(LinkLegacyProfile(AccountId(options["account_id"]), AthleteId(options["profile_id"])))
        except InvalidAthleteData as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                "Vinculación explícita completada; registros conservados. Verificación de correo sigue siendo independiente."
            )
        )
