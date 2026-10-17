from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClassificationViewSet,
    ExerciseViewSet,
    UserExerciseRMViewSet,
    UserViewSet,
    WorkoutDataViewSet,
)

# 📌 1️⃣ Crear el Router para los ViewSets
router_trauning_app = DefaultRouter()
router_trauning_app.register(r"classifications", ClassificationViewSet)
router_trauning_app.register(r"exercises", ExerciseViewSet)
router_trauning_app.register(r"users", UserViewSet)
router_trauning_app.register(r"user-exercise-rm", UserExerciseRMViewSet)
router_trauning_app.register(r"workout-data", WorkoutDataViewSet)

# 📌 2️⃣ Definir las Rutas de la API
urlpatterns = [
    # Todas las rutas de los ViewSets dentro de `/api/`
    path("api/", include(router_trauning_app.urls)),
]
