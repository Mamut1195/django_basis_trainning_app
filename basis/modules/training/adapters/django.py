"""Owner-scoped execution persistence over module-owned Django models."""

from dataclasses import fields
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models

from basis.modules.training.adapters.models import (
    Block,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
)
from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId

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


def save_validated(row: models.Model) -> None:
    row.save()


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
        from basis.adapters.django.account_locks import lock_account

        lock_account(owner, Session.objects.db)

    def prescription(self, owner: AccountId, planned: PlannedSessionId) -> Prescription:
        from .locking import intent_executions, lock_scheduled
        from .models import TrainingPlan

        row = PlannedSession.objects.filter(pk=planned, owner_id=owner).first()
        if row is None:
            raise Unavailable("Prescripción no disponible.")
        row = lock_scheduled(row.pk, row._state.db or "default")
        if (
            TrainingPlan.objects.filter(previous_id=row.plan_id).exists()
            or row.status != "scheduled"
        ):
            raise ValidationError(
                "La prescripción fue sustituida, cancelada u omitida. Consulta la versión actual."
            )
        if intent_executions(row).filter(status="completed").exists():
            raise ValidationError("Esta intención ya se completó y se conserva como historial.")
        return Prescription(
            PlannedSessionId(int(row.pk)),
            owner,
            row.title,
            tuple(block_state(b) for b in row.blocks.all()),
        )

    def active(self, owner: AccountId, planned: PlannedSessionId) -> SessionState | None:
        from .locking import intent_executions

        prescription = PlannedSession.objects.get(owner_id=owner, pk=planned)
        row = intent_executions(prescription).filter(status="in_progress").first()
        return session_state(row) if row is not None else None

    def get(
        self, session: SessionId, *, lock: bool, owner: AccountId | None = None
    ) -> SessionState | None:
        query = Session.objects.all()
        if owner is not None:
            query = query.filter(owner_id=owner)
            if (
                not query.filter(pk=session).exists()
                and Session.objects.filter(pk=session).exists()
            ):
                raise Unavailable("La sesión no está disponible.")
        if lock:
            from .locking import lock_execution

            if query.filter(pk=session).exists():
                lock_execution(session, query.db)
            query = query.select_for_update()
        row = query.filter(pk=session).first()
        return session_state(row) if row is not None else None

    def check_plan(self, owner: AccountId, planned: PlannedSessionId) -> None:
        from .locking import intent_executions

        self.prescription(owner, planned)
        if intent_executions(PlannedSession.objects.get(pk=planned, owner_id=owner)).exists():
            raise InvalidExecution("La intención ya tiene una ejecución. Continúa esa sesión.")

    def save(self, state: SessionState) -> SessionState:
        self.lock_owner(state.owner)
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
