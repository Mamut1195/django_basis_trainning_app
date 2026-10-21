"""Wire shapes and required fixture values for regression scenarios."""

from decimal import Decimal
from typing import TypedDict, TypeVar, cast

from django.contrib.auth.models import AbstractUser

from basis.modules.sync.adapters.actions import sync_session as synchronize
from basis.modules.training.adapters.actions import progress_report as report
from basis.modules.training.adapters.actions import session_snapshot as snapshot
from basis.modules.training.adapters.actions import trip_summary as summary
from basis.modules.training.adapters.models import Session, TrainingPlan, TrekTrip
from basis.modules.training.adapters.planning_actions import build_plan as create_plan

T = TypeVar("T")


def required(value: T | None) -> T:
    assert value is not None, "Expected fixture value"
    return value


class BlockDocument(TypedDict, total=False):
    id: int
    source: int | None
    order: int
    sport: str
    title: str
    notes: str
    target: dict[str, object]
    actual: dict[str, object]
    sets: list[dict[str, object]]
    intervals: list[dict[str, object]]


class ScheduledDocument(TypedDict, total=False):
    title: str
    date: str
    cycle_key: str
    blocks: list[BlockDocument]


class PlanDocument(TypedDict, total=False):
    title: str
    goal_id: int
    start_date: str
    end_date: str
    cycles: list[dict[str, object]]
    sessions: list[ScheduledDocument]
    notes: str


class SessionDocument(TypedDict, total=False):
    id: str
    title: str
    date: str
    status: str
    revision: int
    duration_seconds: int | None
    duration_protocol: str
    reported_rpe: Decimal | str | float | int | None
    planned_id: int | None
    planned: int | None
    notes: str
    blocks: list[BlockDocument]


class SportDocument(TypedDict, total=False):
    sport: str
    label: str
    sessions: int
    distance_m: Decimal | None
    ascent_m: Decimal | None
    external_volume_kg: Decimal | None


class LoadDocument(TypedDict):
    protocol: str
    label: str
    known: int
    missing: int
    value: Decimal


class ProgressDocument(TypedDict):
    sessions: int
    scheduled_past: int
    completed_scheduled: int
    adherence_percent: float | None
    sports: list[SportDocument]
    loads: list[LoadDocument]


class TripDocument(TypedDict):
    stages: int
    completed: int
    totals: dict[str, Decimal]


def build_plan(
    owner: AbstractUser, content: object, previous: TrainingPlan | None = None
) -> TrainingPlan:
    return required(create_plan(owner, content, previous))


def session_snapshot(item: Session) -> SessionDocument:
    return cast(SessionDocument, snapshot(item))


def sync_session(owner: AbstractUser, mutation_id: object, payload: object) -> SessionDocument:
    return cast(SessionDocument, synchronize(owner, mutation_id, payload))


def progress_report(owner: AbstractUser) -> ProgressDocument:
    return cast(ProgressDocument, report(owner))


def trip_summary(item: TrekTrip) -> TripDocument:
    return cast(TripDocument, summary(item))
