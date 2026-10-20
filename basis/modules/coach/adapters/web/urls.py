"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.coach.adapters.web import views as coach

urlpatterns = [
    path("coach/", coach.coach, name="coach"),
    path("coach/ask/", coach.coach_ask, name="coach-ask"),
    path("coach/jobs/<uuid:pk>/", coach.job_detail, name="job-detail"),
    path("coach/proposals/<int:pk>/", coach.proposal_review, name="proposal-review"),
]
