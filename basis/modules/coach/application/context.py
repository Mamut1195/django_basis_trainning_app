"""Compose only public, owner-scoped context ports."""

from basis.modules.athletes.public import AthleteCoachContexts
from basis.modules.catalog.public import CoachExercises
from basis.modules.training.public import TrainingCoachContexts
from basis.shared.identifiers import AccountId, PlanId
from basis.shared.ports import Clock

from ..domain.context import CoachContext
from ..domain.jobs import CoachInvalid, JobKind


class Contexts:
    def __init__(
        self,
        athletes: AthleteCoachContexts,
        training: TrainingCoachContexts,
        exercises: CoachExercises,
        clock: Clock,
    ) -> None:
        self.athletes, self.training, self.exercises, self.clock = (
            athletes,
            training,
            exercises,
            clock,
        )

    def snapshot(
        self, owner: AccountId, kind: JobKind, base_plan_id: PlanId | None
    ) -> CoachContext:
        base = self.training.selected(owner, base_plan_id) if base_plan_id is not None else None
        if base_plan_id is not None and (kind != "plan" or base is None):
            raise CoachInvalid("El plan seleccionado no est\u00e1 disponible.")
        return CoachContext(
            self.clock.now(),
            self.athletes.read(owner),
            self.training.read(owner, self.clock.today()),
            self.exercises.read() if kind == "plan" else None,
            self.training.variables() if kind == "plan" else None,
            base,
        )
