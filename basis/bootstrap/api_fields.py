"""Compose catalog-owned fields into record input serializers."""

from rest_framework import serializers

from basis.modules.catalog.adapters.models import Exercise
from basis.modules.catalog.adapters.serializers import ExerciseSerializer


def exercise_field() -> serializers.Serializer[Exercise]:
    return ExerciseSerializer(read_only=True)


def exercise_reference() -> serializers.PrimaryKeyRelatedField[Exercise]:
    return serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(), source="exercise", write_only=True
    )
