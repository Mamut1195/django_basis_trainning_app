"""Compose module routes and shared technical endpoints."""

from django.urls import include, path

from basis.adapters.web import platform_views as platform
from basis.adapters.web.records import owned_new

urlpatterns = [
    path("", include("basis.modules.training.adapters.web.urls")),
    path("", include("basis.modules.accounts.adapters.web.urls")),
    path("", include("basis.modules.athletes.adapters.web.urls")),
    path("", include("basis.modules.billing.adapters.web.urls")),
    path("", include("basis.modules.coach.adapters.web.urls")),
    path("", include("basis.modules.sync.adapters.web.urls")),
    path("records/<str:resource>/new/", owned_new, name="owned-new"),
    path("export/", platform.export_data, name="export"),
    path("api/csrf/", platform.csrf_api, name="csrf-api"),
    path("manifest.webmanifest", platform.manifest, name="manifest"),
    path("service-worker.js", platform.service_worker, name="service-worker"),
    path("health/", platform.health, name="health"),
]
