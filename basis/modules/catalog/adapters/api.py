from __future__ import annotations

from django.db.models import Q, QuerySet
from rest_framework import permissions, serializers, viewsets
from rest_framework.exceptions import PermissionDenied
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
    def get_queryset(self) -> QuerySet[Exercise]:
        filters = ExerciseFilters(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        archived = values.get("archivado", False)
        if archived and not self.request.user.is_staff:
            raise PermissionDenied("Solo el personal puede consultar el catálogo archivado.")
        rows = self.queryset.filter(archivado=archived)
        for field in ("classification", "variante_de"):
            if field in values:
                rows = rows.filter(**{field + "_id": values[field]})
        # These are explicit descriptive filters, not inferred equipment or
        # physiological equivalence. Combine them with the intended prescription.
        for field in ("equipo", "patron_movimiento", "nivel_fatiga", "variante"):
            if field in values:
                rows = rows.filter(**{field + "__iexact": values[field]})
        if "q" in values:
            term = values["q"]
            rows = rows.filter(Q(nombre__icontains=term) | Q(descripcion__icontains=term))
        return rows

    def perform_destroy(self, instance: Exercise) -> None:
        assert self.request.user.pk is not None
        catalog().delete_exercise(
            DeleteExercise(AccountId(self.request.user.pk), ExerciseId(instance.pk))
        )

    queryset = Exercise.objects.select_related("classification").order_by("nombre", "pk")
    serializer_class = ExerciseSerializer
    permission_classes = [CatalogPermission]


class ExerciseFilters(serializers.Serializer[dict[str, object]]):
    q = serializers.CharField(required=False, max_length=255)
    classification = serializers.IntegerField(required=False, min_value=1)
    variante_de = serializers.IntegerField(required=False, min_value=1)
    equipo = serializers.CharField(required=False, max_length=300)
    patron_movimiento = serializers.CharField(required=False, max_length=100)
    nivel_fatiga = serializers.ChoiceField(required=False, choices=Exercise.NIVEL_FATIGA_CHOICES)
    variante = serializers.CharField(required=False, max_length=150)
    archivado = serializers.BooleanField(required=False)
