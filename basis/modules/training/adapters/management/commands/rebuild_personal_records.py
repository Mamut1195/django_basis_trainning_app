"""Rebuild the materialized personal marks for one or all accounts."""

from argparse import ArgumentParser
from typing import cast

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from basis.bootstrap.records import exercise_choices
from basis.modules.training.adapters.records import rebuild
from basis.shared.identifiers import AccountId


class Command(BaseCommand):
    help = "Recompute personal records from completed sessions (backfill)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--account",
            action="append",
            default=[],
            help="Username to rebuild; repeat for several. Default: all active accounts.",
        )

    def handle(self, *args: object, **options: object) -> None:
        users = get_user_model().objects.filter(is_active=True)
        accounts = cast(list[str], options["account"])
        if accounts:
            users = users.filter(username__in=accounts)
        choices = exercise_choices()
        for user in users.iterator():
            count = rebuild(AccountId(user.pk), choices)
            self.stdout.write(self.style.SUCCESS(f"{user.username}: {count} marcas"))
