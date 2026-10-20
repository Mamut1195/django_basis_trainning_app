"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.sync.adapters.web import views as sync

urlpatterns = [
    path("api/sync/", sync.sync_api, name="sync-api"),
    path("offline/", sync.offline, name="offline"),
]
