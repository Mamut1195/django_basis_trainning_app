"""Owner-scoped, paginated measured marks."""

from datetime import date

from django.core.paginator import Paginator

from basis.modules.athletes.public import MeasuredMark, MeasuredMarkPage
from basis.shared.identifiers import AccountId, ExerciseId, MeasuredRMId

from .models import UserExerciseRM


class DjangoMeasuredMarks:
    def read(
        self,
        owner: AccountId,
        exercise: ExerciseId | None,
        start: date | None,
        end: date | None,
        page: int,
    ) -> MeasuredMarkPage:
        query = UserExerciseRM.objects.filter(
            user__account_id=owner, peso_maximo_rm__gt=0
        ).select_related("exercise")
        if exercise is not None:
            query = query.filter(exercise_id=exercise)
        if start is not None:
            query = query.filter(fecha_registro__gte=start)
        if end is not None:
            query = query.filter(fecha_registro__lte=end)
        result = Paginator(query.order_by("-fecha_registro", "-pk"), 20).get_page(page)
        return MeasuredMarkPage(
            tuple(
                MeasuredMark(
                    MeasuredRMId(row.pk),
                    ExerciseId(row.exercise_id),
                    row.exercise.nombre,
                    row.fecha_registro,
                    row.peso_maximo_rm,
                )
                for row in result
            ),
            result.number,
            result.paginator.num_pages,
            result.paginator.count,
            result.previous_page_number() if result.has_previous() else None,
            result.next_page_number() if result.has_next() else None,
        )
