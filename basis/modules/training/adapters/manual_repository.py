"""Django persistence for incremental manual training commands."""

from dataclasses import fields

from basis.shared.identifiers import (
    AccountId,
    BlockId,
    IntervalId,
    Revision,
    SessionId,
    StrengthSetId,
)

from ..application.manual import BlockContext, IntervalContext, StrengthContext
from ..domain.execution import IntervalData, Metric, StrengthData
from ..domain.manual import ManualSessionData, ParentRef, ParentState, PlannedParent, SessionParent
from .django import model_values
from .models import Block, Interval, PlannedSession, Session, StrengthSet, TrainingPlan
from .wire import encode_metrics, encode_strength, interval, metrics, strength


def strength_data(row: StrengthSet) -> StrengthData:
    return strength(model_values(row, tuple(f.name for f in fields(StrengthData))))


def interval_data(row: Interval) -> IntervalData:
    return interval(model_values(row, tuple(f.name for f in fields(IntervalData))))


def parent_ref(row: Session | PlannedSession) -> ParentRef:
    from basis.shared.identifiers import PlannedSessionId

    return (
        SessionParent(SessionId(row.pk))
        if isinstance(row, Session)
        else PlannedParent(PlannedSessionId(row.pk))
    )


def block_parent(row: Block) -> ParentRef:
    parent = row.session if row.session_id else row.planned
    assert parent is not None
    return parent_ref(parent)


class DjangoManualRepository:
    def parent(
        self, ref: ParentRef, *, lock: bool, owner: AccountId | None = None
    ) -> ParentState | None:
        from .locking import intent_executions, lock_execution, lock_scheduled

        if isinstance(ref, SessionParent):
            sessions = Session.objects.all()
            if owner is not None:
                sessions = sessions.filter(owner_id=owner)
            if lock:
                if sessions.filter(pk=ref.id).exists():
                    lock_execution(ref.id, sessions.db)
                sessions = sessions.select_for_update()
            session = sessions.filter(pk=ref.id).first()
            if session is None:
                return None
            return ParentState(
                ref,
                AccountId(session.owner_id),
                session.date,
                Revision(session.revision),
                completed=session.status == "completed",
                from_prescription=session.planned_id is not None,
            )
        planned_rows = PlannedSession.objects.all()
        if owner is not None:
            planned_rows = planned_rows.filter(owner_id=owner)
        if lock:
            if planned_rows.filter(pk=ref.id).exists():
                lock_scheduled(ref.id, planned_rows.db)
            planned_rows = planned_rows.select_for_update()
        planned = planned_rows.filter(pk=ref.id).first()
        if planned is None:
            return None
        return ParentState(
            ref,
            AccountId(planned.owner_id),
            planned.date,
            Revision(planned.revision),
            frozen=planned.status != "scheduled"
            or intent_executions(planned).exists()
            or TrainingPlan.objects.filter(previous_id=planned.plan_id).exists(),
            versioned_intent=planned.origin_id is not None and bool(planned.plan.change_reason),
        )

    def block(self, id: BlockId) -> BlockContext | None:
        row = Block.objects.select_related("session", "planned").filter(pk=id).first()
        return BlockContext(id, block_parent(row), row.sport, metrics(row.target)) if row else None

    def strength(self, id: StrengthSetId) -> StrengthContext | None:
        row = StrengthSet.objects.filter(pk=id).first()
        return StrengthContext(BlockId(row.block_id), strength_data(row)) if row else None

    def interval(self, id: IntervalId) -> IntervalContext | None:
        row = Interval.objects.filter(pk=id).first()
        return IntervalContext(BlockId(row.block_id), interval_data(row)) if row else None

    def block_count(self, ref: ParentRef) -> int:
        return (
            Block.objects.filter(session_id=ref.id).count()
            if isinstance(ref, SessionParent)
            else Block.objects.filter(planned_id=ref.id).count()
        )

    def create_session(self, id: SessionId, owner: AccountId, data: ManualSessionData) -> None:
        from basis.adapters.django.account_locks import lock_account

        lock_account(owner, Session.objects.db)
        Session.objects.create(
            id=id,
            owner_id=owner,
            title=data.title,
            date=data.date,
            duration_seconds=data.duration_seconds,
            duration_protocol=data.duration_protocol.value,
            reported_rpe=data.reported_rpe,
            notes=data.notes,
        )

    def add_block(self, ref: ParentRef, sport: str, title: str, order: int) -> BlockId:
        row = Block(sport=sport, title=title, order=order)
        if isinstance(ref, SessionParent):
            row.session_id = ref.id
        else:
            row.planned_id = ref.id
        row.save()
        return BlockId(row.pk)

    def advance(self, ref: ParentRef, revision: Revision) -> None:
        if isinstance(ref, SessionParent):
            row = Session.objects.get(pk=ref.id)
            row.revision = revision
            row.save()
        else:
            planned = PlannedSession.objects.get(pk=ref.id)
            planned.revision = revision
            planned.save()

    def save_metrics(self, block: BlockId, metrics: tuple[Metric, ...], *, actual: bool) -> None:
        row = Block.objects.get(pk=block)
        if actual:
            row.actual = encode_metrics(metrics)
        else:
            row.target = encode_metrics(metrics)
        row.save()

    def strength_count(self, block: BlockId) -> int:
        return StrengthSet.objects.filter(block_id=block).count()

    def interval_count(self, block: BlockId) -> int:
        return Interval.objects.filter(block_id=block).count()

    def save_strength(
        self, block: BlockId, data: StrengthData, row: StrengthSetId | None, order: int | None
    ) -> StrengthSetId:
        values = encode_strength(data)
        values["exercise_id"] = values.pop("exercise")
        values["rm_reference_id"] = values.pop("rm_reference")
        instance = (
            StrengthSet.objects.get(pk=row) if row is not None else StrengthSet(block_id=block)
        )
        for key, value in values.items():
            setattr(instance, key, value)
        if order is not None:
            instance.order = order
        instance.save()
        return StrengthSetId(instance.pk)

    def save_interval(
        self, block: BlockId, data: IntervalData, row: IntervalId | None, order: int | None
    ) -> IntervalId:
        instance = Interval.objects.get(pk=row) if row is not None else Interval(block_id=block)
        instance.repetitions = data.repetitions
        instance.target = encode_metrics(data.target)
        instance.actual = encode_metrics(data.actual)
        instance.rest_seconds = data.rest_seconds
        instance.actual_rest_seconds = data.actual_rest_seconds
        instance.target_rpe = data.target_rpe
        instance.actual_rpe = data.actual_rpe
        if order is not None:
            instance.order = order
        instance.save()
        return IntervalId(instance.pk)
