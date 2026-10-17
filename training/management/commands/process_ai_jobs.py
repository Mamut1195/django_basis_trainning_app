import time

from django.core.management.base import BaseCommand

from training.ai import process_one, quarantine_stale_jobs


class Command(BaseCommand):
    help = "Process durable AI jobs; never retries ambiguous provider calls."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            quarantine_stale_jobs()
            worked = process_one()
            if options["once"]:
                return
            if not worked:
                time.sleep(2)
