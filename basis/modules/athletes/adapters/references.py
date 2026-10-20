"""Read measured references without exposing their ORM model to training."""

from basis.modules.athletes.public import RMReference, RMReferences
from basis.shared.identifiers import AccountId, ExerciseId, MeasuredRMId

from .models import UserExerciseRM


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
