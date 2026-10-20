from __future__ import annotations

from rest_framework import serializers

from basis.modules.catalog.adapters.record_actions import save_classification, save_exercise
from basis.shared.text import normalized_name

from .models import Classification, Exercise


class ClassificationSerializer(serializers.ModelSerializer[Classification]):
    def create(self, validated_data: dict[str, object]) -> Classification:
        return save_classification(self.context["request"].user.pk, validated_data)

    def update(self, instance: Classification, validated_data: dict[str, object]) -> Classification:
        return save_classification(self.context["request"].user.pk, validated_data, instance)

    class Meta:
        model = Classification
        fields = ["id", "nombre"]

    def validate_nombre(self, value: str) -> str:
        return normalized_name(value)


class ExerciseSerializer(serializers.ModelSerializer[Exercise]):
    def create(self, validated_data: dict[str, object]) -> Exercise:
        return save_exercise(self.context["request"].user.pk, validated_data)

    def update(self, instance: Exercise, validated_data: dict[str, object]) -> Exercise:
        return save_exercise(self.context["request"].user.pk, validated_data, instance)

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
