import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from daily_trainning_app.models import Classification, Exercise
from daily_trainning_app.models import User as Athlete
from training.models import AthleteSettings, BillingAccount, Goal
from training.proposals import build_plan


class Command(BaseCommand):
    help = "Idempotent, development-only demonstration. Never deletes existing data."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@basis.test")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.DEVELOPMENT_ACCESS:
            raise CommandError(
                "Activa DEBUG y BASIS_DEVELOPMENT_ACCESS solo en una base local de demostración."
            )
        password = os.getenv("BASIS_DEMO_PASSWORD")
        if not password or len(password) < 10:
            raise CommandError("Define BASIS_DEMO_PASSWORD con al menos diez caracteres.")
        email = options["email"].strip().lower()
        user, created = get_user_model().objects.get_or_create(
            username=email, defaults={"email": email, "first_name": "Atleta de demostración"}
        )
        if created:
            user.set_password(password)
            user.save()
        if Athlete.objects.filter(email__iexact=email).exclude(account=user).exists():
            raise CommandError("Ya existe un perfil sin vincular; no se asignará automáticamente.")
        Athlete.objects.get_or_create(
            account=user,
            defaults={
                "nombre": "Atleta de demostración",
                "email": email,
                "fecha_inicio": timezone.localdate(),
                "email_verified": True,
                "edad": 25,
                "objetivos": "Mejorar fuerza y resistencia con constancia",
            },
        )
        AthleteSettings.objects.get_or_create(
            owner=user, defaults={"availability": [1, 3, 5], "equipment": "Mancuernas y gimnasio"}
        )
        BillingAccount.objects.get_or_create(owner=user)
        classification, _ = Classification.objects.get_or_create(nombre="Fuerza general")
        for name in (
            "Sentadilla",
            "Peso muerto rumano",
            "Press de banca",
            "Remo con mancuerna",
            "Plancha",
        ):
            Exercise.objects.get_or_create(nombre=name, classification=classification)
        goal, _ = Goal.objects.get_or_create(
            owner=user, title="Demostración: construir una base", defaults={"sport": "running"}
        )
        if not user.trainingplan_set.exists():
            start = timezone.localdate().isoformat()
            end = (timezone.localdate() + timedelta(days=6)).isoformat()
            build_plan(
                user,
                {
                    "title": "Demostración: una semana con intención",
                    "goal_id": goal.pk,
                    "start_date": start,
                    "end_date": end,
                    "cycles": [
                        {
                            "key": "macro",
                            "parent": None,
                            "kind": "macro",
                            "title": "Base",
                            "start_date": start,
                            "end_date": end,
                        },
                        {
                            "key": "meso",
                            "parent": "macro",
                            "kind": "meso",
                            "title": "Constancia",
                            "start_date": start,
                            "end_date": end,
                        },
                        {
                            "key": "micro",
                            "parent": "meso",
                            "kind": "micro",
                            "title": "Semana inicial",
                            "start_date": start,
                            "end_date": end,
                        },
                    ],
                    "sessions": [
                        {
                            "title": "Demostración: rodaje suave",
                            "date": start,
                            "cycle_key": "micro",
                            "blocks": [
                                {
                                    "sport": "running",
                                    "title": "Rodaje",
                                    "target": {"duration_seconds": 1800},
                                }
                            ],
                        },
                        {
                            "title": "Demostración: senderismo",
                            "date": end,
                            "cycle_key": "micro",
                            "blocks": [
                                {
                                    "sport": "hiking",
                                    "title": "Sendero",
                                    "target": {"duration_seconds": 7200},
                                }
                            ],
                        },
                    ],
                },
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Demostración preparada sin borrar registros. La contraseña de una cuenta existente no se cambia."
            )
        )
