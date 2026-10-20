import time

from django.core.management.base import BaseCommand, CommandParser

from basis.modules.coach.adapters.actions import process_one, quarantine_stale_jobs


class Command(BaseCommand):
    help = "Process durable AI jobs; never retries ambiguous provider calls."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--once", action="store_true")

    def handle(self, *args: object, **options: object) -> None:
        while True:
            quarantine_stale_jobs()
            worked = process_one()
            if options["once"]:
                return
            if not worked:
                time.sleep(2)
