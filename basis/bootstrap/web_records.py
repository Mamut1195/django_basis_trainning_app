"""Route resource creation to its owning module's input adapter."""

from django.http import HttpRequest, HttpResponse

from basis.modules.athletes.adapters.views import owned_new as athlete_record
from basis.modules.training.adapters.views import owned_new as training_record


def owned_new(request: HttpRequest, resource: str) -> HttpResponse:
    return (
        training_record(request, resource)
        if resource in ("goal", "trip")
        else athlete_record(request, resource)
    )
