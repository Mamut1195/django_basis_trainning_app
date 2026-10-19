from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers

from daily_trainning_app.models import Classification, Exercise, User, UserExerciseRM, WorkoutData
from daily_trainning_app.strength_metrics import METRICS_VERSION


class ClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classification
        fields = ["id", "nombre"]

    def validate_nombre(self, value):
        return " ".join(value.split()).title()


class ExerciseSerializer(serializers.ModelSerializer):
    classification = ClassificationSerializer(read_only=True)
    classification_id = serializers.PrimaryKeyRelatedField(
        queryset=Classification.objects.all(), source="classification", write_only=True
    )

    class Meta:
        model = Exercise
        fields = [
            "id",
            "nombre",
            "video",
            "descripcion",
            "classification",
            "classification_id",
            "nivel_fatiga",
            "patron_movimiento",
            "musculos_principales",
            "equipo",
            "variante",
            "archivado",
        ]


class UserSerializer(serializers.ModelSerializer):
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

    def validate_email(self, value):
        return value.strip().lower()


class OwnedRecordSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.none(), source="user", write_only=True, required=False
    )
    exercise = ExerciseSerializer(read_only=True)
    exercise_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(), source="exercise", write_only=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["user_id"].queryset = User.objects.filter(account=request.user)

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except ModelValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"non_field_errors": exc.messages}
            ) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except ModelValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"non_field_errors": exc.messages}
            ) from exc


class UserExerciseRMSerializer(OwnedRecordSerializer):
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

    def validate_peso_maximo_rm(self, value):
        if value <= 0:
            raise serializers.ValidationError("El 1RM debe ser mayor a 0.")
        return value


class WorkoutDataSerializer(OwnedRecordSerializer):
    def validate(self, attrs):
        if "rm_referencia" in self.initial_data:
            raise serializers.ValidationError(
                {"rm_referencia": "La referencia histórica se asigna en el servidor."}
            )
        return super().validate(attrs)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        verified = instance.metrics_version == METRICS_VERSION
        if (
            not verified
            or not instance.rm_referencia_id
            or instance.rm_referencia.peso_maximo_rm <= 0
        ):
            data["intensidad_relativa"] = None
            data["volumen_relativo"] = None
        if not verified or not instance.rm_sesion:
            data["rm_sesion"] = None
        return data

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
