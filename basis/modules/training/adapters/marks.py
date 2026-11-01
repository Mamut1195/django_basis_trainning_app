"""Paginated owner-scoped eligible estimates using the existing series calculation."""

from datetime import date

from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Coalesce, NullIf

from basis.modules.training.public import EstimatedMark, EstimatedMarkPage
from basis.shared.identifiers import AccountId, ExerciseId, SessionId, StrengthSetId

from .models import StrengthSet


class DjangoEstimatedMarks:
    def read(
        self,
        owner: AccountId,
        exercise: ExerciseId | None,
        start: date | None,
        end: date | None,
        page: int,
    ) -> EstimatedMarkPage:
        query = (
            StrengthSet.objects.filter(
                block__session__owner_id=owner,
                block__session__status="completed",
                actual_kg__gt=0,
                actual_reps__gte=1,
                actual_reps__lte=10,
                actual_rpe=10,
            )
            .annotate(
                effective_kind=Coalesce(NullIf("actual_kind", Value("")), "kind"),
                effective_load=Coalesce(NullIf("actual_load_type", Value("")), "load_type"),
            )
            .filter(effective_kind="work", effective_load="external")
            .select_related("exercise", "actual_exercise", "block__session")
        )
        if exercise is not None:
            query = query.filter(
                Q(actual_exercise_id=exercise)
                | Q(actual_exercise__isnull=True, exercise_id=exercise)
            )
        if start is not None:
            query = query.filter(block__session__date__gte=start)
        if end is not None:
            query = query.filter(block__session__date__lte=end)
        result = Paginator(
            query.order_by("-block__session__date", "-block__session_id", "-pk"), 20
        ).get_page(page)
        rows = []
        for row in result:
            value = row.estimated_1rm
            assert (
                value is not None
                and row.actual_kg is not None
                and row.actual_reps is not None
                and row.actual_rpe is not None
            )
            session = row.block.session
            assert session is not None
            actual = row.actual_exercise or row.exercise
            rows.append(
                EstimatedMark(
                    StrengthSetId(row.pk),
                    ExerciseId(actual.pk),
                    actual.nombre,
                    session.date,
                    SessionId(session.pk),
                    session.title,
                    row.block.title,
                    row.order,
                    value,
                    row.actual_kg,
                    row.actual_reps,
                    row.actual_rpe,
                )
            )
        return EstimatedMarkPage(
            tuple(rows),
            result.number,
            result.paginator.num_pages,
            result.paginator.count,
            result.previous_page_number() if result.has_previous() else None,
            result.next_page_number() if result.has_next() else None,
        )
