from rest_framework.routers import DefaultRouter

from basis.modules.athletes.adapters.api import (
    UserExerciseRMViewSet,
    UserViewSet,
    WorkoutDataViewSet,
)
from basis.modules.catalog.adapters.api import ClassificationViewSet, ExerciseViewSet

api_router = DefaultRouter()
api_router.register(r"classifications", ClassificationViewSet)
api_router.register(r"exercises", ExerciseViewSet)
api_router.register(r"users", UserViewSet)
api_router.register(r"user-exercise-rm", UserExerciseRMViewSet)
api_router.register(r"workout-data", WorkoutDataViewSet)
