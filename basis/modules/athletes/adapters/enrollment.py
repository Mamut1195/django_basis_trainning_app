"""Enrollment over existing tables in the caller's transaction."""

from datetime import date

from basis.shared.identifiers import AccountId, AthleteId
from daily_trainning_app.models import User as Athlete
from training.models import AthleteSettings

from ..domain.records import require_legacy_link


class DjangoAthleteEnrollment:
    def enroll(self, account: AccountId, name: str, email: str, started_on: date) -> None:
        Athlete.objects.create(
            account_id=account, nombre=name, email=email, fecha_inicio=started_on
        )
        AthleteSettings.objects.create(owner_id=account)

    def verify_email(self, account: AccountId) -> None:
        Athlete.objects.filter(account_id=account).update(email_verified=True)

    def exists(self, account: AccountId) -> bool:
        return Athlete.objects.filter(account_id=account).exists()

    def email_exists(self, email: str) -> bool:
        return Athlete.objects.filter(email__iexact=email).exists()

    def link_legacy(self, account: AccountId, email: str, profile: AthleteId) -> None:
        row = Athlete.objects.select_for_update().get(pk=profile)
        require_legacy_link(
            AccountId(row.account_id) if row.account_id is not None else None,
            account,
            Athlete.objects.filter(account_id=account).exclude(pk=profile).exists(),
            row.email,
            email,
        )
        row.account_id = account
        row.full_clean()
        row.save(update_fields=["account"])
