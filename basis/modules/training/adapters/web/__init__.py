"""Public route handlers for training presentation."""

from django.http import HttpRequest, HttpResponse

from basis.adapters.web.framework import write_required

from .execution import (
    block_metrics,
    block_new,
    block_redirect,
    get_parent,
    owned_block,
    session_detail,
    session_edit,
    session_new,
    snapshot_api,
)
from .intervals import interval_edit, interval_new
from .planning import (
    cycle_new,
    goal_new,
    plan_detail,
    plan_list,
    plan_new,
    plan_revise,
    scheduled_detail,
    scheduled_new,
    scheduled_reschedule,
    scheduled_start,
    today,
)
from .progress import progress
from .strength import set_edit, set_new
from .trekking import stage_new, trip_detail, trip_new


@write_required
def owned_new(request: HttpRequest, resource: str) -> HttpResponse:
    if resource == "goal":
        return goal_new(request)
    if resource == "trip":
        return trip_new(request)
    return HttpResponse(status=404)


__all__ = [
    "today",
    "plan_list",
    "plan_new",
    "plan_detail",
    "plan_revise",
    "cycle_new",
    "scheduled_new",
    "scheduled_detail",
    "scheduled_start",
    "scheduled_reschedule",
    "session_new",
    "session_detail",
    "session_edit",
    "get_parent",
    "block_redirect",
    "block_new",
    "owned_block",
    "block_metrics",
    "snapshot_api",
    "set_edit",
    "set_new",
    "interval_edit",
    "interval_new",
    "progress",
    "trip_detail",
    "stage_new",
    "owned_new",
]
