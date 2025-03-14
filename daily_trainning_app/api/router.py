from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClassificationViewSet, ExerciseViewSet, UserViewSet,
    UserExerciseRMViewSet, WorkoutDataViewSet
)

# 📌 1️⃣ Crear el Router para los ViewSets
router_trauning_app = DefaultRouter()
router_trauning_app.register(r'classifications', ClassificationViewSet)
router_trauning_app.register(r'exercises', ExerciseViewSet)
router_trauning_app.register(r'users', UserViewSet)
router_trauning_app.register(r'user-exercise-rm', UserExerciseRMViewSet)
router_trauning_app.register(r'workout-data', WorkoutDataViewSet)

# 📌 2️⃣ Definir las Rutas de la API
urlpatterns = [
    path('api/', include(router_trauning_app.urls)),  # Todas las rutas de los ViewSets dentro de `/api/`
]
