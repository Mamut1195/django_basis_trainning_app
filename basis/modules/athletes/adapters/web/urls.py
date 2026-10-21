"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.athletes.adapters.web import views as athletes

urlpatterns = [
    path("profile/", athletes.profile, name="profile"),
    path("profile/edit/", athletes.profile_edit, name="profile-edit"),
    path("profile/preferences/", athletes.preferences_edit, name="preferences-edit"),
    path("profile/sports/<int:pk>/edit/", athletes.sport_edit, name="sport-edit"),
    path("profile/measurements/", athletes.measurement_history, name="measurement-history"),
    path("measurements/rm/new/", athletes.rm_new, name="rm-new"),
]
