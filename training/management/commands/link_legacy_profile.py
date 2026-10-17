from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from daily_trainning_app.models import User as Athlete


class Command(BaseCommand):
    help = "Explicit operator-only mapping; never guesses owners by IDs or emails."

    def add_arguments(self, parser):
        parser.add_argument("--account-id", type=int, required=True)
        parser.add_argument("--profile-id", type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        account = get_user_model().objects.select_for_update().get(pk=options["account_id"])
        profile = Athlete.objects.select_for_update().get(pk=options["profile_id"])
        if profile.account_id and profile.account_id != account.pk:
            raise CommandError("El perfil ya está vinculado a otra cuenta.")
        if Athlete.objects.filter(account=account).exclude(pk=profile.pk).exists():
            raise CommandError("La cuenta ya tiene otro perfil. No se fusiona automáticamente.")
        if profile.email.casefold() != account.email.casefold():
            raise CommandError(
                "Los correos no coinciden. Verifica la titularidad antes de continuar."
            )
        profile.account = account
        profile.full_clean()
        profile.save(update_fields=["account"])
        self.stdout.write(
            self.style.SUCCESS(
                "Vinculación explícita completada; registros conservados. Verificación de correo sigue siendo independiente."
            )
        )
