"""Compose an owner date through the public athlete presentation port only."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings

from basis.bootstrap.presentation import athlete_reads
from basis.shared.identifiers import AccountId


def owner_date(owner: AccountId, instant: datetime) -> date:
    profiles = athlete_reads()
    return instant.astimezone(ZoneInfo(profiles.timezone(owner) or settings.TIME_ZONE)).date()
