"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.athletes.adapters.web import views as athletes

urlpatterns = [
    path("profile/", athletes.profile, name="profile"),
    path("profile/edit/", athletes.profile_edit, name="profile-edit"),
    path("profile/preferences/", athletes.preferences_edit, name="preferences-edit"),
    path("measurements/rm/new/", athletes.rm_new, name="rm-new"),
]
