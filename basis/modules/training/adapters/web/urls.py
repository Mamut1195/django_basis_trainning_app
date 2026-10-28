"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.training.adapters import web as training
from basis.modules.training.adapters.web import editor

urlpatterns = [
    path("plans/from-template/", editor.template_new, name="plan-template"),
    path("plans/<int:pk>/calendar/", editor.calendar, name="plan-calendar"),
    path("plans/<int:pk>/edit/", editor.plan_edit, name="plan-edit"),
    path("plans/<int:pk>/editor/cycles/new/", editor.cycle_editor, name="editor-cycle-new"),
    path("plans/<int:pk>/editor/cycles/<int:cycle_id>/", editor.cycle_editor, name="editor-cycle"),
    path("plans/<int:pk>/editor/sessions/new/", editor.session_new, name="editor-session-new"),
    path("scheduled/<int:pk>/editor/<str:action>/", editor.session_action, name="editor-session"),
    path("", training.today, name="today"),
    path("plans/", training.plan_list, name="plans"),
    path("plans/new/", training.plan_new, name="plan-new"),
    path("plans/<int:pk>/", training.plan_detail, name="plan-detail"),
    path("plans/<int:pk>/revise/", training.plan_revise, name="plan-revise"),
    path("plans/<int:pk>/restore/<int:target>/", training.plan_restore, name="plan-restore"),
    path("plans/<int:pk>/cycles/new/", training.cycle_new, name="cycle-new"),
    path("scheduled/new/", training.scheduled_new, name="scheduled-new"),
    path("scheduled/<int:pk>/", training.scheduled_detail, name="scheduled-detail"),
    path("scheduled/<int:pk>/start/", training.scheduled_start, name="scheduled-start"),
    path("scheduled/<int:pk>/change/", training.scheduled_change, name="scheduled-change"),
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
