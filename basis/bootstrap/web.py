from django.urls import path

from basis.bootstrap import platform_views as platform
from basis.bootstrap.web_records import owned_new
from basis.modules.accounts.adapters import views as accounts
from basis.modules.athletes.adapters import views as athletes
from basis.modules.billing.adapters import views as billing
from basis.modules.coach.adapters import views as coach
from basis.modules.sync.adapters import views as sync
from basis.modules.training.adapters import views as training

urlpatterns = [
    path("", training.today, name="today"),
    path("accounts/signup/", accounts.signup, name="signup"),
    path("accounts/verify/<str:token>/", accounts.verify_email, name="verify-email"),
    path("accounts/verification/", accounts.resend_verification, name="resend-verification"),
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
    path("profile/", athletes.profile, name="profile"),
    path("profile/edit/", athletes.profile_edit, name="profile-edit"),
    path("profile/preferences/", athletes.preferences_edit, name="preferences-edit"),
    path("records/<str:resource>/new/", owned_new, name="owned-new"),
    path("measurements/rm/new/", athletes.rm_new, name="rm-new"),
    path("trekking/<int:pk>/", training.trip_detail, name="trip-detail"),
    path("trekking/<int:pk>/stages/new/", training.stage_new, name="stage-new"),
    path("billing/", billing.billing_page, name="billing"),
    path("billing/<str:action>/", billing.billing_action, name="billing-action"),
    path("webhooks/polar/", billing.polar_webhook, name="polar-webhook"),
    path("coach/", coach.coach, name="coach"),
    path("coach/ask/", coach.coach_ask, name="coach-ask"),
    path("coach/jobs/<uuid:pk>/", coach.job_detail, name="job-detail"),
    path("coach/proposals/<int:pk>/", coach.proposal_review, name="proposal-review"),
    path("api/sessions/<uuid:pk>/snapshot/", training.snapshot_api, name="snapshot-api"),
    path("api/sync/", sync.sync_api, name="sync-api"),
    path("export/", platform.export_data, name="export"),
    path("api/csrf/", platform.csrf_api, name="csrf-api"),
    path("offline/", sync.offline, name="offline"),
    path("manifest.webmanifest", platform.manifest, name="manifest"),
    path("service-worker.js", platform.service_worker, name="service-worker"),
    path("health/", platform.health, name="health"),
]
