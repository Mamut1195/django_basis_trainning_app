from __future__ import annotations

from rest_framework import permissions, viewsets
from rest_framework.request import Request
from rest_framework.views import APIView

from basis.bootstrap.catalog import catalog
from basis.modules.catalog.public import DeleteClassification, DeleteExercise, catalog_allowed
from basis.shared.identifiers import AccountId, ClassificationId, ExerciseId

from .models import Classification, Exercise
from .serializers import ClassificationSerializer, ExerciseSerializer


class CatalogPermission(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return catalog_allowed(
            request.user.is_authenticated,
            request.user.is_staff,
            request.method in permissions.SAFE_METHODS,
        )


class ClassificationViewSet(viewsets.ModelViewSet[Classification]):
    def perform_destroy(self, instance: Classification) -> None:
        assert self.request.user.pk is not None
        catalog().delete_classification(
            DeleteClassification(AccountId(self.request.user.pk), ClassificationId(instance.pk))
        )

    queryset = Classification.objects.order_by("nombre")
    serializer_class = ClassificationSerializer
    permission_classes = [CatalogPermission]


class ExerciseViewSet(viewsets.ModelViewSet[Exercise]):
    def perform_destroy(self, instance: Exercise) -> None:
        assert self.request.user.pk is not None
        catalog().delete_exercise(
            DeleteExercise(AccountId(self.request.user.pk), ExerciseId(instance.pk))
        )

    queryset = (
        Exercise.objects.select_related("classification").filter(archivado=False).order_by("nombre")
    )
    serializer_class = ExerciseSerializer
    permission_classes = [CatalogPermission]
