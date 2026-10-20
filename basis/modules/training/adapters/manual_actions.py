"""Form input conversion and framework error translation for manual cases."""

from collections.abc import Callable
from typing import TypeVar, cast
from uuid import UUID

from django.core.exceptions import ValidationError
from django.http import Http404

from basis.bootstrap.manual_training import manual_training
from basis.bootstrap.training import snapshot
from basis.shared.identifiers import (
    AccountId,
    BlockId,
    IntervalId,
    PlannedSessionId,
    Revision,
    SessionId,
    StrengthSetId,
)

from ..application.manual import (
    AddBlock,
    CreateManualSession,
    SaveBlockMetrics,
    SaveInterval,
    SaveStrength,
)
from ..domain.execution import DurationProtocol, Unavailable
from ..domain.manual import (
    FormPolicy,
    ManualConflict,
    ManualInvalid,
    ManualSessionData,
    ParentRef,
    ParentState,
    PlannedParent,
    SessionParent,
    form_policy,
)
from ..domain.planning import InvalidPlanning
from ..domain.sports import InvalidSportMetrics
from .manual_repository import interval_data, parent_ref, strength_data
from .models import Block, Interval, PlannedSession, Session, StrengthSet
from .wire import metrics

T = TypeVar("T")


def translated(owner: int, operation: Callable[[], T]) -> T:
    try:
        return operation()
    except Unavailable as error:
        raise Http404 from error
    except ManualConflict as error:
        # Imported here at the web composition boundary, never by the core.
        from basis.bootstrap.web_framework import Conflict
        current = snapshot(owner, error.current.ref.id) if isinstance(error.current.ref, SessionParent) else None
        raise Conflict(current) from None
    except (ManualInvalid, InvalidPlanning, InvalidSportMetrics, ValueError) as error:
        raise ValidationError(str(error)) from None


def parse_parent(kind: str, id: int | str | UUID | None) -> ParentRef:
    try:
        if kind == "session":
            return SessionParent(SessionId(UUID(str(id))))
        if kind == "planned":
            return PlannedParent(PlannedSessionId(int(str(id))))
    except (ValueError, TypeError):
        pass
    raise Http404


def inspect_parent(owner: int, ref: ParentRef) -> ParentState:
    return translated(owner, lambda: manual_training().inspect(AccountId(owner), ref))


def inspect_metadata(owner: int, ref: ParentRef) -> None:
    translated(owner, lambda: manual_training().inspect_metadata(AccountId(owner), ref))


def edit_form_policy(owner: int, parent: Session | PlannedSession) -> FormPolicy:
    return form_policy(inspect_parent(owner, parent_ref(parent)))


def expected_revision(value: object) -> Revision:
    try:
        return Revision(int(cast(str | int, value)))
    except (TypeError, ValueError):
        raise ValidationError("Recarga la página antes de guardar.") from None


def create_session(owner: int, row: Session, sport: str, title: str) -> SessionId:
    data = ManualSessionData(row.title, row.date, row.duration_seconds,
                            DurationProtocol(row.duration_protocol), row.reported_rpe, row.notes)
    return translated(owner, lambda: manual_training().create(CreateManualSession(AccountId(owner), data, sport, title)))


def add_block(owner: int, parent: Session | PlannedSession, revision: object, sport: str, title: str) -> BlockId:
    command = AddBlock(AccountId(owner), parent_ref(parent), expected_revision(revision), sport, title)
    return translated(owner, lambda: manual_training().add_block(command))


def save_metrics(owner: int, block: Block, revision: object, data: dict[str, object]) -> None:
    command = SaveBlockMetrics(AccountId(owner), BlockId(block.pk), expected_revision(revision), metrics(data))
    translated(owner, lambda: manual_training().save_metrics(command))


def save_strength(owner: int, row: StrengthSet, revision: object, *, creating: bool) -> None:
    command = SaveStrength(AccountId(owner), BlockId(row.block_id), expected_revision(revision),
                           strength_data(row), None if creating else StrengthSetId(row.pk))
    translated(owner, lambda: manual_training().save_strength(command))


def save_interval(owner: int, row: Interval, revision: object, *, creating: bool) -> None:
    command = SaveInterval(AccountId(owner), BlockId(row.block_id), expected_revision(revision),
                           interval_data(row), None if creating else IntervalId(row.pk))
    translated(owner, lambda: manual_training().save_interval(command))
