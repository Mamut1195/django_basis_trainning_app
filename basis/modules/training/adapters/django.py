"""Django persistence adapter over stable legacy tables and model registration."""

from dataclasses import fields
from typing import Protocol, cast
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import models

from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId
from training.models import Block, Interval, PlannedSession, Session, StrengthSet

from ..domain.execution import (
    BlockData,
    DurationProtocol,
    IntervalData,
    InvalidExecution,
    Prescription,
    SessionState,
    SessionStatus,
    StrengthData,
    Unavailable,
)
from .wire import encode_metrics, encode_strength, interval, metrics, strength


class _LegacySave(Protocol):
    def save(self) -> None: ...


def save_validated(row: models.Model) -> None:
    # Transitional signature bridge: ValidatedModel.save is still unannotated.
    # Keep its real full_clean + save behavior; remove bridge when ORM is typed.
    cast(_LegacySave, row).save()


def model_values(row: models.Model, names: tuple[str, ...]) -> dict[str, object]:
    return {
        name: getattr(row, name + "_id" if name in ("exercise", "rm_reference") else name)
        for name in names
    }


def block_state(row: Block) -> BlockData:
    return BlockData(
        id=int(row.pk),
        order=row.order,
        sport=row.sport,
        title=row.title,
        target=metrics(row.target),
        actual=metrics(row.actual),
        notes=row.notes,
        sets=tuple(
            strength(model_values(s, tuple(f.name for f in fields(StrengthData))))
            for s in row.sets.all()
        ),
        intervals=tuple(
            interval(model_values(i, tuple(f.name for f in fields(IntervalData))))
            for i in row.intervals.all()
        ),
    )


def session_state(row: Session) -> SessionState:
    return SessionState(
        id=SessionId(row.pk),
        owner=AccountId(int(row.owner_id)),
        date=row.date,
        title=row.title,
        revision=Revision(row.revision),
        status=SessionStatus(row.status),
        planned=PlannedSessionId(int(row.planned_id)) if row.planned_id is not None else None,
        duration_seconds=row.duration_seconds,
        duration_protocol=DurationProtocol(row.duration_protocol),
        reported_rpe=row.reported_rpe,
        notes=row.notes,
        blocks=tuple(block_state(b) for b in row.blocks.all()),
    )


class UUIDSessionIds:
    def new(self) -> SessionId:
        return SessionId(uuid4())



class DjangoSessionRepository:
    def lock_owner(self, owner: AccountId) -> None:
        get_user_model().objects.select_for_update().get(pk=owner)

    def prescription(self, owner: AccountId, planned: PlannedSessionId) -> Prescription:
        row = PlannedSession.objects.select_for_update().filter(pk=planned, owner_id=owner).first()
        if row is None:
            raise Unavailable("Prescripción no disponible.")
        return Prescription(
            PlannedSessionId(int(row.pk)),
            owner,
            row.title,
            tuple(block_state(b) for b in row.blocks.all()),
        )

    def active(self, owner: AccountId, planned: PlannedSessionId) -> SessionState | None:
        row = Session.objects.filter(
            owner_id=owner, planned_id=planned, status="in_progress"
        ).first()
        return session_state(row) if row is not None else None

    def get(self, session: SessionId, *, lock: bool) -> SessionState | None:
        query = Session.objects.all()
        if lock:
            query = query.select_for_update()
        row = query.filter(pk=session).first()
        return session_state(row) if row is not None else None

    def check_plan(self, owner: AccountId, planned: PlannedSessionId) -> None:
        if not PlannedSession.objects.filter(pk=planned, owner_id=owner).exists():
            raise InvalidExecution("Prescripción no disponible.")

    def save(self, state: SessionState) -> SessionState:
        row = Session.objects.filter(pk=state.id).first()
        if row is None:
            row = Session(id=state.id, owner_id=state.owner)
        row.title = state.title
        row.date = state.date
        row.planned_id = state.planned
        row.status = state.status.value
        row.duration_seconds = state.duration_seconds
        row.duration_protocol = state.duration_protocol.value
        row.reported_rpe = state.reported_rpe
        row.notes = state.notes
        row.revision = int(state.revision)
        save_validated(row)
        for old in row.blocks.all():
            old.sets.all().delete()
            old.intervals.all().delete()
        row.blocks.all().delete()
        if not 1 <= len(state.blocks) <= 30:
            raise InvalidExecution("Una sesión necesita entre 1 y 30 bloques.")
        for order, block in enumerate(state.blocks, 1):
            created = Block.objects.create(
                session=row,
                order=order,
                sport=block.sport,
                title=block.title,
                target=encode_metrics(block.target),
                actual=encode_metrics(block.actual),
                notes=block.notes,
            )
            for index, item in enumerate(block.sets, 1):
                values = encode_strength(item)
                values["exercise_id"] = values.pop("exercise")
                values["rm_reference_id"] = values.pop("rm_reference")
                StrengthSet.objects.create(block=created, order=index, **values)
            for index, segment in enumerate(block.intervals, 1):
                Interval.objects.create(
                    block=created,
                    order=index,
                    repetitions=segment.repetitions,
                    target=encode_metrics(segment.target),
                    actual=encode_metrics(segment.actual),
                    rest_seconds=segment.rest_seconds,
                    actual_rest_seconds=segment.actual_rest_seconds,
                    target_rpe=segment.target_rpe,
                    actual_rpe=segment.actual_rpe,
                )
        return session_state(row)
