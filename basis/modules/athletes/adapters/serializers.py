from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TypedDict, TypeVar, Unpack, cast

from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.request import Request

from basis.bootstrap.api_fields import exercise_field, exercise_reference
from basis.modules.athletes.adapters.record_actions import write_legacy_rm, write_legacy_workout
from basis.modules.athletes.public import InvalidAthleteData, require_positive_rm
from basis.modules.training.public import METRICS_VERSION

from .models import User, UserExerciseRM, WorkoutData


class SerializerOptions(TypedDict, total=False):
    many: bool
    read_only: bool
    write_only: bool
    required: bool
    source: str
    label: str
    allow_null: bool


class UserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "nombre",
            "email",
            "fecha_inicio",
            "titulo",
            "pais",
            "ciudad",
            "especialidad",
            "edad",
            "peso",
            "objetivos",
            "descripcion",
        ]

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


RecordT = TypeVar("RecordT", bound=UserExerciseRM | WorkoutData)


class OwnedRecordSerializer(serializers.ModelSerializer[RecordT]):
    user: serializers.PrimaryKeyRelatedField[User] = serializers.PrimaryKeyRelatedField(
        read_only=True
    )
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.none(), source="user", write_only=True, required=False
    )
    exercise = exercise_field()
    exercise_id = exercise_reference()

    def __init__(
        self,
        instance: RecordT | None = None,
        data: object = empty,
        *,
        context: Mapping[str, object] | None = None,
        partial: bool = False,
        **kwargs: Unpack[SerializerOptions],
    ) -> None:
        super().__init__(
            instance=instance, data=data, context=context or {}, partial=partial, **kwargs
        )
        request = cast(Request | None, self.context.get("request"))
        if request and request.user.is_authenticated:
            self.fields["user_id"] = serializers.PrimaryKeyRelatedField(
                queryset=User.objects.filter(account_id=request.user.pk),
                source="user",
                write_only=True,
                required=False,
            )

    def create(self, validated_data: dict[str, object]) -> RecordT:
        try:
            writer = write_legacy_rm if self.Meta.model is UserExerciseRM else write_legacy_workout
            return cast(RecordT, writer(self.context["request"].user.pk, validated_data))
        except ModelValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"non_field_errors": exc.messages}
            ) from exc

    def update(self, instance: RecordT, validated_data: dict[str, object]) -> RecordT:
        try:
            if isinstance(instance, UserExerciseRM):
                return cast(
                    RecordT,
                    write_legacy_rm(self.context["request"].user.pk, validated_data, instance),
                )
            return cast(
                RecordT,
                write_legacy_workout(self.context["request"].user.pk, validated_data, instance),
            )
        except ModelValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"non_field_errors": exc.messages}
            ) from exc


class UserExerciseRMSerializer(OwnedRecordSerializer[UserExerciseRM]):
    class Meta:
        model = UserExerciseRM
        fields = [
            "id",
            "user",
            "user_id",
            "exercise",
            "exercise_id",
            "peso_maximo_rm",
            "fecha_registro",
        ]

    def validate_peso_maximo_rm(self, value: Decimal) -> Decimal:
        try:
            require_positive_rm(value)
        except InvalidAthleteData as error:
            raise serializers.ValidationError(str(error)) from error
        return value


class WorkoutDataSerializer(OwnedRecordSerializer[WorkoutData]):
    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if "rm_referencia" in self.initial_data:
            raise serializers.ValidationError(
                {"rm_referencia": "La referencia histórica se asigna en el servidor."}
            )
        return cast(dict[str, object], super().validate(attrs))

    def to_representation(self, instance: WorkoutData) -> dict[str, object]:
        data = super().to_representation(instance)
        verified = instance.metrics_version == METRICS_VERSION
        if (
            not verified
            or instance.rm_referencia is None
            or instance.rm_referencia.peso_maximo_rm <= 0
        ):
            data["intensidad_relativa"] = None
            data["volumen_relativo"] = None
        if not verified or not instance.rm_sesion:
            data["rm_sesion"] = None
        return cast(dict[str, object], data)

    class Meta:
        model = WorkoutData
        fields = [
            "id",
            "user",
            "user_id",
            "exercise",
            "exercise_id",
            "fecha",
            "sets",
            "reps",
            "total_reps",
            "peso",
            "carga",
            "intensidad_relativa",
            "volumen_relativo",
            "rpe_objetivo",
            "rpe_real",
            "rm_sesion",
            "rm_referencia",
            "metrics_version",
        ]
        read_only_fields = [
            "total_reps",
            "carga",
            "intensidad_relativa",
            "volumen_relativo",
            "rm_sesion",
            "rm_referencia",
            "metrics_version",
        ]
