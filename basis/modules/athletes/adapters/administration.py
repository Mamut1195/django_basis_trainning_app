"""Administrative persistence is confined to athlete-owned models."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from basis.shared.identifiers import AccountId, AthleteId, ExerciseId, MeasuredRMId, WorkoutId

from ..application.administration import AdministrativeProfile, Operation, Resource
from ..domain.records import MeasuredRMData, MeasuredRMState, WorkoutData
from ..domain.workouts import WorkoutCalculation, WorkoutContext
from .django import apply_calculation, assign, workout_context_for
from .models import User, UserExerciseRM
from .models import WorkoutData as WorkoutRow


class DjangoAdministrativeAuthorization:
    def require(self, actor: AccountId, resource: Resource, operation: Operation) -> None:
        user = get_user_model().objects.get(pk=actor)
        model = {"profile": "user", "rm": "userexerciserm", "workout": "workoutdata"}[resource]
        if (
            not user.is_active
            or not user.is_staff
            or not user.has_perm(f"basis_athletes.{operation}_{model}")
        ):
            raise PermissionDenied


class DjangoAdministrativeRecords:
    def save_profile(self, data: AdministrativeProfile, id: AthleteId | None) -> AthleteId:
        row = User.objects.get(pk=id) if id is not None else User()
        assign(row, data.profile)
        row.account_id, row.public_id = data.account, data.public_id
        row.email_verified, row.email, row.fecha_inicio = (
            data.email_verified,
            data.email,
            data.joined,
        )
        row.save()
        return AthleteId(row.pk)

    def rm_previous(self, id: MeasuredRMId | None) -> MeasuredRMState | None:
        if id is None:
            return None
        row = UserExerciseRM.objects.select_for_update().get(pk=id)
        return MeasuredRMState(
            AthleteId(row.user_id),
            MeasuredRMData(ExerciseId(row.exercise_id), row.peso_maximo_rm, row.fecha_registro),
        )

    def save_rm(
        self, athlete: AthleteId, data: MeasuredRMData, id: MeasuredRMId | None
    ) -> MeasuredRMId:
        row = UserExerciseRM.objects.get(pk=id) if id is not None else UserExerciseRM()
        row.user_id = athlete
        assign(row, data)
        row.save()
        return MeasuredRMId(row.pk)

    def workout_context(
        self, athlete: AthleteId, data: WorkoutData, id: WorkoutId | None
    ) -> WorkoutContext:
        row = (
            WorkoutRow.objects.select_for_update().filter(pk=id).first() if id is not None else None
        )
        # Administrative ownership changes historically rebuild the dated context.
        if row is not None and row.user_id != athlete:
            from ..domain.workouts import PreviousWorkout
            from .django import measured_reference, workout_data

            context = workout_context_for(User.objects.get(pk=athlete), data, None)
            return WorkoutContext(
                athlete,
                PreviousWorkout(
                    AthleteId(row.user_id),
                    workout_data(row),
                    measured_reference(row.rm_referencia),
                    row.metrics_version,
                ),
                context.dated_reference,
            )
        return workout_context_for(User.objects.get(pk=athlete), data, id)

    def save_workout(
        self,
        athlete: AthleteId,
        data: WorkoutData,
        id: WorkoutId | None,
        calculation: WorkoutCalculation,
    ) -> WorkoutId:
        row = WorkoutRow.objects.get(pk=id) if id is not None else WorkoutRow()
        row.user_id = athlete
        assign(row, data)
        apply_calculation(row, calculation)
        row.save()
        return WorkoutId(row.pk)

    def delete_profiles(self, ids: tuple[AthleteId, ...]) -> None:
        User.objects.filter(pk__in=ids).delete()

    def delete_rms(self, ids: tuple[MeasuredRMId, ...]) -> None:
        UserExerciseRM.objects.filter(pk__in=ids).delete()

    def delete_workouts(self, ids: tuple[WorkoutId, ...]) -> None:
        WorkoutRow.objects.filter(pk__in=ids).delete()
