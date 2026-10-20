from __future__ import annotations

from typing import TypeVar

from django.db.models import QuerySet
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response

from basis.adapters.web.permissions import require_write_access

from .models import User, UserExerciseRM, WorkoutData
from .serializers import UserExerciseRMSerializer, UserSerializer, WorkoutDataSerializer


class UserViewSet(viewsets.ReadOnlyModelViewSet[User]):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[User]:
        return User.objects.filter(account_id=self.request.user.pk).order_by("pk")


RecordT = TypeVar("RecordT", bound=UserExerciseRM | WorkoutData)


class PrivateRecordViewSet(viewsets.ModelViewSet[RecordT]):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[RecordT]:
        return super().get_queryset().filter(user__account_id=self.request.user.pk).order_by("-pk")

    def profile(self) -> User:
        profile = User.objects.filter(account_id=self.request.user.pk).first()
        if not profile:
            raise PermissionDenied("La cuenta no tiene un perfil vinculado.")
        return profile

    def perform_create(self, serializer: serializers.BaseSerializer[RecordT]) -> None:
        require_write_access(self.request.user)
        serializer.save(user=self.profile())

    def perform_update(self, serializer: serializers.BaseSerializer[RecordT]) -> None:
        require_write_access(self.request.user)
        serializer.save(user=self.profile())

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        self.get_object()
        return Response(
            {"detail": "Conservamos el historial. Puedes corregir el registro."}, status=409
        )


class UserExerciseRMViewSet(PrivateRecordViewSet[UserExerciseRM]):
    queryset = UserExerciseRM.objects.select_related("user", "exercise__classification")
    serializer_class = UserExerciseRMSerializer


class WorkoutDataViewSet(PrivateRecordViewSet[WorkoutData]):
    queryset = WorkoutData.objects.select_related(
        "user", "exercise__classification", "rm_referencia"
    )
    serializer_class = WorkoutDataSerializer

    @action(detail=False, methods=["get"])
    def latest(self, request: Request) -> Response:
        latest = self.get_queryset().order_by("-fecha", "-pk").first()
        return Response(self.get_serializer(latest).data if latest else None)
