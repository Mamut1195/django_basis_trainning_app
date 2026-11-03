"""Compose only public, owner-scoped context ports."""

from dataclasses import replace
from datetime import timedelta

from basis.modules.athletes.public import AthleteCoachContexts
from basis.modules.catalog.public import CoachExercises
from basis.modules.training.public import TrainingCoachContexts
from basis.shared.identifiers import AccountId, PlanId
from basis.shared.ports import Clock

from ..domain.context import CoachContext
from ..domain.jobs import CoachInvalid, JobKind
from ..domain.prompts import INSTRUCTIONS_VERSION, PLAN_FORMAT, SYSTEM, instructions_digest


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
        now, today = self.clock.now(), self.clock.today()
        athlete = self.athletes.read(owner)
        training = self.training.read(owner, today)
        start = training.scope.start if training.scope else today - timedelta(days=13)
        # Future or stale declarations are not current recovery evidence. Their
        # absence is explicit; nothing is inferred from gaps between sessions.
        wellness = athlete.wellness
        if wellness is not None and not start <= wellness.date <= today:
            wellness = None
        if wellness is not None:
            wellness = replace(
                wellness,
                sleep_quality=None,
                resting_hr_bpm=None,
                hrv_ms=None,
                hrv_method="",
                notes="",
            )
        preferences = athlete.preferences
        if preferences is not None:
            preferences = replace(
                preferences,
                equipment=preferences.equipment[:500],
                limitations=preferences.limitations[:500],
                timezone_name="",
            )
        athlete = replace(
            athlete,
            preferences=preferences,
            wellness=wellness,
            sports=tuple(
                replace(
                    s,
                    threshold=None,
                    threshold_unit="",
                    measured_on=None,
                    method="",
                    threshold_kind="",
                    threshold_source="",
                )
                if s.measured_on is not None and s.measured_on > today
                else s
                for s in athlete.sports
            ),
        )
        p = athlete.preferences
        missing = [
            name
            for name, absent in (
                ("age", athlete.age is None),
                ("objectives", not athlete.objectives.strip() and not training.goals),
                ("structured_goals", not training.goals),
                ("availability", p is None or not p.availability),
                ("minutes_per_session", p is None),
                ("equipment", p is None or not p.equipment.strip()),
                ("history_in_selection", not training.recent),
                ("wellness_in_period", wellness is None),
                ("effective_recovery", True),
                ("strength_rm_not_consulted", True),
                (
                    "adherence_not_consulted",
                    training.scope is not None and not training.scope.adherence_included,
                ),
            )
            if absent
        ]
        missing.extend(f"threshold:{s.sport}" for s in athlete.sports if s.threshold is None)
        if wellness is not None:
            missing.extend(
                f"wellness:{name}"
                for name, value in (
                    ("sleep_hours", wellness.sleep_hours),
                    ("fatigue", wellness.fatigue),
                    ("stress", wellness.stress),
                    ("soreness", wellness.soreness),
                    ("readiness", wellness.readiness),
                    ("pain_score", wellness.pain_score),
                )
                if value is None
            )
        return CoachContext(
            now,
            athlete,
            training,
            self.exercises.read() if kind == "plan" else None,
            self.training.variables() if kind == "plan" else None,
            base,
            schema_version=2,
            missing=tuple(missing),
            instructions_version=INSTRUCTIONS_VERSION,
            system_sha256=instructions_digest(SYSTEM),
            plan_sha256=instructions_digest(PLAN_FORMAT) if kind == "plan" else None,
            tools=("athletes.coach.read/v1", "training.coach.read/v2")
            + (("training.coach.selected/v1",) if base is not None else ())
            + (("catalog.coach.read/v1", "training.coach.variables/v1") if kind == "plan" else ()),
        )
