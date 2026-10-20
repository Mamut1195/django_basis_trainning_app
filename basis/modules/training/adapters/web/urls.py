"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.training.adapters import web as training

urlpatterns = [
    path("", training.today, name="today"),
    path("plans/", training.plan_list, name="plans"),
    path("plans/new/", training.plan_new, name="plan-new"),
    path("plans/<int:pk>/", training.plan_detail, name="plan-detail"),
    path("plans/<int:pk>/revise/", training.plan_revise, name="plan-revise"),
    path("plans/<int:pk>/cycles/new/", training.cycle_new, name="cycle-new"),
    path("scheduled/new/", training.scheduled_new, name="scheduled-new"),
    path("scheduled/<int:pk>/", training.scheduled_detail, name="scheduled-detail"),
    path("scheduled/<int:pk>/start/", training.scheduled_start, name="scheduled-start"),
    path(
        "scheduled/<int:pk>/reschedule/", training.scheduled_reschedule, name="scheduled-reschedule"
    ),
    path("sessions/new/", training.session_new, name="session-new"),
    path("sessions/<uuid:pk>/", training.session_detail, name="session-detail"),
    path("sessions/<uuid:pk>/edit/", training.session_edit, name="session-edit"),
    path("blocks/parent/<str:kind>/<str:pk>/new/", training.block_new, name="block-new"),
    path("blocks/<int:pk>/metrics/", training.block_metrics, name="block-metrics"),
    path("blocks/<int:pk>/sets/new/", training.set_new, name="set-new"),
    path("sets/<int:pk>/edit/", training.set_edit, name="set-edit"),
    path("intervals/<int:pk>/edit/", training.interval_edit, name="interval-edit"),
    path("blocks/<int:pk>/intervals/new/", training.interval_new, name="interval-new"),
    path("progress/", training.progress, name="progress"),
    path("trekking/<int:pk>/", training.trip_detail, name="trip-detail"),
    path("trekking/<int:pk>/stages/new/", training.stage_new, name="stage-new"),
    path("api/sessions/<uuid:pk>/snapshot/", training.snapshot_api, name="snapshot-api"),
]
