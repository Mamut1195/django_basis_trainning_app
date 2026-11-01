"""Owner-scoped coach projection; no unrelated identity/contact data."""

from basis.modules.athletes.adapters.models import AthleteSettings, SportProfile
from basis.modules.athletes.adapters.models import User as Athlete
from basis.shared.identifiers import AccountId

from ..application.coach import AthleteCoachContext
from .django import preferences_data, sport_data, wellness_data, wellness_rows


class DjangoAthleteCoachContexts:
    def read(self, owner: AccountId) -> AthleteCoachContext:
        profile = Athlete.objects.get(account_id=owner)
        preferences = AthleteSettings.objects.filter(owner_id=owner).first()
        wellness = wellness_rows(owner).first()
        return AthleteCoachContext(
            profile.edad,
            (profile.objetivos or "")[:300],
            preferences_data(preferences) if preferences else None,
            tuple(sport_data(s) for s in SportProfile.objects.filter(owner_id=owner)),
            wellness_data(wellness) if wellness else None,
        )
