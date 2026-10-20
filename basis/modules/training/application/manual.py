"""Incremental manual writes coordinated through specific persistence ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol

from basis.shared.identifiers import (
    AccountId,
    BlockId,
    ExerciseId,
    IntervalId,
    MeasuredRMId,
    PlannedSessionId,
    Revision,
    SessionId,
    StrengthSetId,
)
from basis.shared.ports import UnitOfWork

from ..domain.execution import IntervalData, Metric, StrengthData, Unavailable
from ..domain.manual import (
    EmptyPrescription,
    ManualSessionData,
    ParentRef,
    ParentState,
    PlannedParent,
    next_revision,
    require_interval_prescription,
    require_parent,
    require_strength_prescription,
    validate_heading,
    validate_interval,
    validate_session,
    validate_strength,
)
from ..domain.sports import validate_sport_metrics
from ..domain.strength import validate_strength_reference
from .execution import SessionIds, WriteAuthorization

if TYPE_CHECKING:
    from basis.modules.athletes.public import RMReferences


@dataclass(frozen=True)
class BlockContext:
    id: BlockId
    parent: ParentRef
    sport: str


@dataclass(frozen=True)
class StrengthContext:
    block: BlockId
    data: StrengthData


@dataclass(frozen=True)
class IntervalContext:
    block: BlockId
    data: IntervalData


@dataclass(frozen=True)
class CreateManualSession:
    owner: AccountId
    data: ManualSessionData
    sport: str
    block_title: str


@dataclass(frozen=True)
class AddBlock:
    owner: AccountId
    parent: ParentRef
    revision: Revision
    sport: str
    title: str


@dataclass(frozen=True)
class SaveBlockMetrics:
    owner: AccountId
    block: BlockId
    revision: Revision
    metrics: tuple[Metric, ...]


@dataclass(frozen=True)
class SaveStrength:
    owner: AccountId
    block: BlockId
    revision: Revision
    data: StrengthData
    row: StrengthSetId | None = None


@dataclass(frozen=True)
class SaveInterval:
    owner: AccountId
    block: BlockId
    revision: Revision
    data: IntervalData
    row: IntervalId | None = None


class ManualRepository(Protocol):
    def parent(self, ref: ParentRef, *, lock: bool) -> ParentState | None: ...
    def block(self, id: BlockId) -> BlockContext | None: ...
    def strength(self, id: StrengthSetId) -> StrengthContext | None: ...
    def interval(self, id: IntervalId) -> IntervalContext | None: ...
    def block_count(self, ref: ParentRef) -> int: ...
    def create_session(self, id: SessionId, owner: AccountId, data: ManualSessionData) -> None: ...
    def add_block(self, ref: ParentRef, sport: str, title: str, order: int) -> BlockId: ...
    def advance(self, ref: ParentRef, revision: Revision) -> None: ...
    def save_metrics(
        self, block: BlockId, metrics: tuple[Metric, ...], *, actual: bool
    ) -> None: ...
    def strength_count(self, block: BlockId) -> int: ...
    def interval_count(self, block: BlockId) -> int: ...
    def save_strength(
        self, block: BlockId, data: StrengthData, row: StrengthSetId | None, order: int | None
    ) -> StrengthSetId: ...
    def save_interval(
        self, block: BlockId, data: IntervalData, row: IntervalId | None, order: int | None
    ) -> IntervalId: ...


class ManualTraining:
    def __init__(
        self,
        repository: ManualRepository,
        uow: Callable[[], UnitOfWork],
        authorization: WriteAuthorization,
        ids: SessionIds,
        references: RMReferences,
    ) -> None:
        self.repository = repository
        self.uow = uow
        self.authorization = authorization
        self.ids = ids
        self.references = references

    def inspect(self, owner: AccountId, ref: ParentRef) -> ParentState:
        return require_parent(self.repository.parent(ref, lock=False), owner)

    def inspect_metadata(self, owner: AccountId, ref: ParentRef) -> ParentState:
        current = self.repository.parent(ref, lock=False)
        if current is None or current.owner != owner or current.completed:
            raise Unavailable("Session unavailable")
        return require_parent(current, owner)

    def start_preflight(self, owner: AccountId, planned: PlannedSessionId) -> None:
        # Starting an existing prescription is permitted even after a prior execution.
        current = self.repository.parent(PlannedParent(planned), lock=False)
        if current is None or current.owner != owner:
            raise Unavailable("Prescripción no disponible.")
        if self.repository.block_count(current.ref) == 0:
            raise EmptyPrescription("Añade al menos un bloque antes de comenzar.")

    def create(self, command: CreateManualSession) -> SessionId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            validate_session(command.data)
            validate_heading(command.sport, command.block_title)
            id = self.ids.new()
            self.repository.create_session(id, command.owner, command.data)
            from ..domain.manual import SessionParent

            self.repository.add_block(SessionParent(id), command.sport, command.block_title, 1)
            work.commit()
            return id

    def _lock(self, owner: AccountId, ref: ParentRef, expected: Revision) -> ParentState:
        self.authorization.require(owner)
        current = self.repository.parent(ref, lock=True)
        if current is None:
            raise Unavailable("La sesión no está disponible.")
        revision = next_revision(current, owner, expected)
        self.repository.advance(ref, revision)
        return current

    def _block(self, owner: AccountId, id: BlockId) -> BlockContext:
        block = self.repository.block(id)
        if block is None:
            raise Unavailable("Bloque no disponible.")
        self.inspect(owner, block.parent)
        return block

    def add_block(self, command: AddBlock) -> BlockId:
        with self.uow() as work:
            self._lock(command.owner, command.parent, command.revision)
            validate_heading(command.sport, command.title)
            result = self.repository.add_block(
                command.parent,
                command.sport,
                command.title,
                self.repository.block_count(command.parent) + 1,
            )
            work.commit()
            return result

    def save_metrics(self, command: SaveBlockMetrics) -> None:
        with self.uow() as work:
            block = self._block(command.owner, command.block)
            parent = self._lock(command.owner, block.parent, command.revision)
            metrics = validate_sport_metrics(block.sport, command.metrics)
            self.repository.save_metrics(
                block.id, metrics, actual=not isinstance(parent.ref, PlannedParent)
            )
            work.commit()

    def save_strength(self, command: SaveStrength) -> StrengthSetId:
        with self.uow() as work:
            block = self._block(command.owner, command.block)
            parent = self._lock(command.owner, block.parent, command.revision)
            if command.row is not None:
                current = self.repository.strength(command.row)
                if current is None or current.block != block.id:
                    raise Unavailable("Serie no disponible.")
                if parent.from_prescription:
                    require_strength_prescription(current.data, command.data)
            validate_strength(block.sport, parent, command.data)
            if command.data.rm_reference is not None:
                reference = self.references.get(MeasuredRMId(command.data.rm_reference))
                validate_strength_reference(
                    reference.owner if reference else None,
                    reference.exercise if reference else None,
                    reference.measured_on if reference else None,
                    command.owner,
                    ExerciseId(command.data.exercise),
                    parent.date,
                )
            result = self.repository.save_strength(
                block.id,
                command.data,
                command.row,
                self.repository.strength_count(block.id) + 1 if command.row is None else None,
            )
            work.commit()
            return result

    def save_interval(self, command: SaveInterval) -> IntervalId:
        with self.uow() as work:
            block = self._block(command.owner, command.block)
            parent = self._lock(command.owner, block.parent, command.revision)
            if command.row is not None:
                current = self.repository.interval(command.row)
                if current is None or current.block != block.id:
                    raise Unavailable("Intervalo no disponible.")
                if parent.from_prescription:
                    require_interval_prescription(current.data, command.data)
            validate_interval(block.sport, parent, command.data)
            result = self.repository.save_interval(
                block.id,
                command.data,
                command.row,
                self.repository.interval_count(block.id) + 1 if command.row is None else None,
            )
            work.commit()
            return result
