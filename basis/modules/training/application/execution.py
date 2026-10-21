"""Execution use cases; synchronization receipt policy stays in its adapter."""

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Protocol

from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId
from basis.shared.ports import Clock, UnitOfWork

from ..domain.execution import (
    BlockData,
    DurationProtocol,
    InvalidExecution,
    Prescription,
    SessionState,
    SessionStatus,
    Unavailable,
    require_editable,
    start_execution,
)


@dataclass(frozen=True)
class Change[T]:
    value: T


@dataclass(frozen=True)
class SessionChanges:
    blocks: tuple[BlockData, ...]
    title: Change[str] | None = None
    date: Change[date] | None = None
    status: Change[SessionStatus] | None = None
    planned: PlannedSessionId | None = None
    duration_seconds: Change[int | None] | None = None
    duration_protocol: Change[DurationProtocol] | None = None
    reported_rpe: Change[Decimal | None] | None = None
    notes: Change[str] | None = None


@dataclass(frozen=True)
class StartSession:
    owner: AccountId
    planned: PlannedSessionId


@dataclass(frozen=True)
class ReadSession:
    owner: AccountId
    session: SessionId


@dataclass(frozen=True)
class SessionMutation:
    owner: AccountId
    session: SessionId
    revision: Revision


@dataclass(frozen=True)
class RecordSession(SessionMutation):
    changes: SessionChanges


@dataclass(frozen=True)
class FinishSession(RecordSession):
    pass


class SessionRepository(Protocol):
    def lock_owner(self, owner: AccountId) -> None: ...

    def prescription(self, owner: AccountId, planned: PlannedSessionId) -> Prescription: ...
    def active(self, owner: AccountId, planned: PlannedSessionId) -> SessionState | None: ...
    def get(
        self, session: SessionId, *, lock: bool, owner: AccountId | None = None
    ) -> SessionState | None: ...
    def save(self, state: SessionState) -> SessionState: ...
    def check_plan(self, owner: AccountId, planned: PlannedSessionId) -> None: ...


class WriteAuthorization(Protocol):
    def require(self, owner: AccountId) -> None: ...


class SessionIds(Protocol):
    def new(self) -> SessionId: ...


class Training:
    def __init__(
        self,
        repository: SessionRepository,
        uow: Callable[[], UnitOfWork],
        authorization: WriteAuthorization,
        clock: Clock,
        ids: SessionIds,
        local_date: Callable[[AccountId, datetime], date] | None = None,
    ) -> None:
        self.repository = repository
        self.uow = uow
        self.authorization = authorization
        self.clock = clock
        self.ids = ids
        self.local_date = local_date

    def today(self, owner: AccountId) -> date:
        return self.local_date(owner, self.clock.now()) if self.local_date else self.clock.today()

    def start(self, command: StartSession) -> SessionState:
        with self.uow() as work:
            self.repository.lock_owner(command.owner)
            self.authorization.require(command.owner)
            prescribed = self.repository.prescription(command.owner, command.planned)
            existing = self.repository.active(command.owner, command.planned)
            if existing is not None:
                work.commit()
                return existing
            result = self.repository.save(
                start_execution(prescribed, self.ids.new(), self.today(command.owner))
            )
            work.commit()
            return result

    def read(self, command: ReadSession) -> SessionState:
        current = self.repository.get(command.session, lock=False, owner=command.owner)
        if current is None or current.owner != command.owner:
            raise Unavailable("La sesión no está disponible.")
        return current

    def record(self, command: RecordSession) -> SessionState:
        return self.record_from(command, lambda: command.changes)

    def record_from(
        self, command: SessionMutation, source: Callable[[], SessionChanges]
    ) -> SessionState:
        # Defer boundary conversion until revision/owner guards have run. Offline
        # clients must still receive 409 for stale/completed state before data errors.
        with self.uow() as work:
            self.repository.lock_owner(command.owner)
            self.authorization.require(command.owner)
            current = self.repository.get(command.session, lock=True, owner=command.owner)
            if current is None:
                if command.revision != 0:
                    raise InvalidExecution("Una sesión nueva empieza en revisión cero.")
                current = SessionState(command.session, command.owner, self.today(command.owner))
                revision = Revision(1)
            else:
                revision = require_editable(current, command.owner, command.revision)
            changes = source()
            if current.planned is not None and changes.planned not in (None, current.planned):
                raise InvalidExecution("La ejecución conserva su prescripción original.")
            if not 1 <= len(changes.blocks) <= 30:
                raise InvalidExecution("Una sesión necesita entre 1 y 30 bloques.")
            if any(len(b.sets) > 100 or len(b.intervals) > 100 for b in changes.blocks):
                raise InvalidExecution("Demasiadas series o intervalos.")
            if changes.planned is not None and changes.planned != current.planned:
                self.repository.check_plan(command.owner, changes.planned)
            candidate = replace(
                current,
                revision=revision,
                blocks=changes.blocks,
                title=changes.title.value if changes.title else current.title,
                date=changes.date.value if changes.date else current.date,
                status=changes.status.value if changes.status else current.status,
                planned=changes.planned if changes.planned is not None else current.planned,
                duration_seconds=changes.duration_seconds.value
                if changes.duration_seconds
                else current.duration_seconds,
                duration_protocol=changes.duration_protocol.value
                if changes.duration_protocol
                else current.duration_protocol,
                reported_rpe=changes.reported_rpe.value
                if changes.reported_rpe
                else current.reported_rpe,
                notes=changes.notes.value if changes.notes else current.notes,
            )
            result = self.repository.save(candidate)
            work.commit()
            return result

    def finish(self, command: FinishSession) -> SessionState:
        return self.record(
            replace(
                command, changes=replace(command.changes, status=Change(SessionStatus.COMPLETED))
            )
        )
