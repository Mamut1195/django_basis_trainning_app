from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from basis.bootstrap.catalog import catalog
from basis.modules.catalog.public import DeleteClassification, DeleteExercise, catalog_allowed
from basis.shared.identifiers import AccountId, ClassificationId, ExerciseId
from daily_trainning_app.models import Classification, Exercise, User, UserExerciseRM, WorkoutData
from training.access import require_write_access

from .serializers import (
    ClassificationSerializer,
    ExerciseSerializer,
    UserExerciseRMSerializer,
    UserSerializer,
    WorkoutDataSerializer,
)


class CatalogPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return catalog_allowed(request.user.is_authenticated, request.user.is_staff,
                               request.method in permissions.SAFE_METHODS)


class ClassificationViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        catalog().delete_classification(DeleteClassification(
            AccountId(self.request.user.pk), ClassificationId(instance.pk)))

    queryset = Classification.objects.order_by("nombre")
    serializer_class = ClassificationSerializer
    permission_classes = [CatalogPermission]


class ExerciseViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        catalog().delete_exercise(DeleteExercise(
            AccountId(self.request.user.pk), ExerciseId(instance.pk)))

    queryset = (
        Exercise.objects.select_related("classification").filter(archivado=False).order_by("nombre")
    )
    serializer_class = ExerciseSerializer
    permission_classes = [CatalogPermission]


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(account=self.request.user).order_by("pk")


class PrivateRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user__account=self.request.user).order_by("-pk")

    def profile(self):
        profile = User.objects.filter(account=self.request.user).first()
        if not profile:
            raise PermissionDenied("La cuenta no tiene un perfil vinculado.")
        return profile

    def perform_create(self, serializer):
        require_write_access(self.request.user)
        serializer.save(user=self.profile())

    def perform_update(self, serializer):
        require_write_access(self.request.user)
        serializer.save(user=self.profile())

    def destroy(self, request, *args, **kwargs):
        self.get_object()
        return Response(
            {"detail": "Conservamos el historial. Puedes corregir el registro."}, status=409
        )


class UserExerciseRMViewSet(PrivateRecordViewSet):
    queryset = UserExerciseRM.objects.select_related("user", "exercise__classification")
    serializer_class = UserExerciseRMSerializer


class WorkoutDataViewSet(PrivateRecordViewSet):
    queryset = WorkoutData.objects.select_related(
        "user", "exercise__classification", "rm_referencia"
    )
    serializer_class = WorkoutDataSerializer

    @action(detail=False, methods=["get"])
    def latest(self, request):
        latest = self.get_queryset().order_by("-fecha", "-pk").first()
        return Response(self.get_serializer(latest).data if latest else None)
