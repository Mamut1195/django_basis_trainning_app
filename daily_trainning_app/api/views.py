from rest_framework import viewsets, permissions
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import action
from daily_trainning_app.models import Classification, Exercise, User, UserExerciseRM, WorkoutData
from .serializers import (
    ClassificationSerializer, ExerciseSerializer, UserSerializer,
    UserExerciseRMSerializer, WorkoutDataSerializer
)

# 📌 1️⃣ Vista para Clasificación (List, Create, Retrieve, Update, Delete)


class ClassificationViewSet(viewsets.ModelViewSet):
    queryset = Classification.objects.all()
    serializer_class = ClassificationSerializer
    # Cualquiera puede ver, pero solo autenticados pueden modificar
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


# 📌 2️⃣ Vista para Ejercicios (Filtrado por Clasificación)
class ExerciseViewSet(viewsets.ModelViewSet):
    queryset = Exercise.objects.select_related("classification").all()
    serializer_class = ExerciseSerializer
    # permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    # def get_queryset(self):
    #     """ Filtrar ejercicios por clasificación si se pasa `classification_id` como parámetro """
    #     queryset = super().get_queryset()
    #     classification_id = self.request.query_params.get("classification_id")
    #     if classification_id:
    #         queryset = queryset.filter(classification_id=classification_id)
    #     return queryset


# 📌 3️⃣ Vista para Usuarios (Sin Exponer Datos Sensibles)
class UserViewSet(viewsets.ReadOnlyModelViewSet):  # Solo lectura
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # Solo usuarios autenticados pueden ver usuarios
    # permission_classes = [permissions.IsAuthenticated]


# 📌 4️⃣ Vista para 1RM por Usuario y Ejercicio
class UserExerciseRMViewSet(viewsets.ModelViewSet):
    queryset = UserExerciseRM.objects.select_related("user", "exercise").all()
    serializer_class = UserExerciseRMSerializer
    # permission_classes = [permissions.IsAuthenticated]

    # def get_queryset(self):
    #     """ Filtrar registros de 1RM por usuario autenticado """
    #     if self.request.user.is_superuser:
    #         return super().get_queryset()  # Admins ven todos los datos
    #     return super().get_queryset().filter(
    #         user=self.request.user)  # Usuarios ven solo sus datos

    def perform_create(self, serializer):
        """ Asignar automáticamente el usuario autenticado al crear un registro """
        serializer.save(user=self.request.user)


# 📌 5️⃣ Vista para Entrenamientos (WorkoutData)
class WorkoutDataViewSet(viewsets.ModelViewSet):
    queryset = WorkoutData.objects.select_related("user", "exercise").all()
    serializer_class = WorkoutDataSerializer
    # permission_classes = [permissions.IsAuthenticated]

    # def get_queryset(self):
    #     """ Filtrar entrenamientos por usuario autenticado """
    #     if self.request.user.is_superuser:
    #         return super().get_queryset()
    #     return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        """ Asignar usuario autenticado y calcular valores antes de guardar """
        instance = serializer.save(user=self.request.user)
        # Asegurar cálculos automáticos de carga, RPE, volumen, etc.
        instance.clean()
        instance.save()

    @action(detail=True, methods=["get"])
    def latest(self, request, pk=None):
        """ Obtener el entrenamiento más reciente de un usuario """
        user = get_object_or_404(User, pk=pk)
        latest_workout = WorkoutData.objects.filter(
            user=user).order_by("-fecha").first()
        if latest_workout:
            serializer = self.get_serializer(latest_workout)
            return Response(serializer.data)
        return Response(
            {"message": "No hay entrenamientos para este usuario."}, status=404)
