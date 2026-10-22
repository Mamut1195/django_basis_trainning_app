"""Read measured references without exposing their ORM model to training."""

from datetime import date

from django.utils import timezone

from basis.modules.athletes.public import RMReference, RMReferences, SportThreshold, SportThresholds
from basis.shared.identifiers import AccountId, ExerciseId, MeasuredRMId

from .models import SportProfile, UserExerciseRM


class DjangoRMReferences(RMReferences):
    def get(self, reference: MeasuredRMId) -> RMReference | None:
        row = UserExerciseRM.objects.select_related("user").filter(pk=int(reference)).first()
        if row is None:
            return None
        return RMReference(
            AccountId(row.user.account_id) if row.user.account_id is not None else None,
            ExerciseId(row.exercise_id),
            row.fecha_registro,
        )


class DjangoSportThresholds(SportThresholds):
    def current(
        self, owner: AccountId, sport: str, through: date, *, using: str = "default"
    ) -> SportThreshold | None:
        # One current profile per owner/sport. Never reconstruct an older value from
        # today's mutable row when prescribing a past date.
        row = (
            SportProfile.objects.using(using)
            .filter(
                owner_id=owner,
                sport=sport,
                threshold__isnull=False,
                measured_on__lte=min(through, timezone.localdate()),
            )
            .first()
        )
        if row is None or row.threshold is None or row.measured_on is None:
            return None
        return SportThreshold(
            row.pk,
            row.sport,
            row.threshold,
            row.threshold_unit,
            row.measured_on,
            row.method,
            row.threshold_kind,
            row.threshold_source,
        )
