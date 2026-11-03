"""Owner-scoped coach projection; no unrelated identity/contact data."""

from django.db import transaction
from django.db.transaction import TransactionManagementError

from basis.modules.athletes.adapters.models import AthleteSettings, SportProfile
from basis.modules.athletes.adapters.models import User as Athlete
from basis.shared.identifiers import AccountId

from ..application.coach import AthleteCoachContext
from .django import preferences_data, sport_data, wellness_data, wellness_rows


class DjangoAthleteCoachContexts:
    def read_for_acceptance(self, owner: AccountId) -> AthleteCoachContext:
        """Caller holds account before aggregate locks; never open an inner UoW.

        The profile anchors official profile/sport/wellness writes, including
        sport inserts. Existing preferences need their own row lock because
        their official free editor does not take either anchor.
        """
        if not transaction.get_connection(Athlete.objects.db).in_atomic_block:
            raise TransactionManagementError("Acceptance context requires an open unit of work")
        profile = Athlete.objects.select_for_update().get(account_id=owner)
        preferences = AthleteSettings.objects.select_for_update().filter(owner_id=owner).first()
        sports = tuple(
            SportProfile.objects.select_for_update().filter(owner_id=owner).order_by("pk")
        )
        wellness = wellness_rows(owner).first()
        return AthleteCoachContext(
            profile.edad,
            (profile.objetivos or "")[:300],
            preferences_data(preferences) if preferences else None,
            tuple(sport_data(s) for s in sports),
            wellness_data(wellness) if wellness else None,
        )

    def read(self, owner: AccountId) -> AthleteCoachContext:
        profile = Athlete.objects.get(account_id=owner)
        preferences = AthleteSettings.objects.filter(owner_id=owner).first()
        wellness = wellness_rows(owner).first()
        return AthleteCoachContext(
            profile.edad,
            (profile.objetivos or "")[:300],
            preferences_data(preferences) if preferences else None,
            tuple(
                sport_data(s) for s in SportProfile.objects.filter(owner_id=owner).order_by("pk")
            ),
            wellness_data(wellness) if wellness else None,
        )
