"""Resolve observation dates in the account's configured time zone."""

from datetime import date
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .models.profile import AthleteSettings


def owner_local_date(owner_id: int | None, *, using: str = "default") -> date:
    zone = None
    if owner_id is not None:
        zone = (
            AthleteSettings.objects.using(using)
            .filter(owner_id=owner_id)
            .values_list("timezone_name", flat=True)
            .first()
        )
    return timezone.now().astimezone(ZoneInfo(zone or settings.TIME_ZONE)).date()
