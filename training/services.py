"""Transactional application services shared by web, offline sync and AI proposals."""

import uuid
from decimal import Decimal
from typing import Callable, cast

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models, transaction

from basis.bootstrap import planning
from basis.bootstrap import progress as progress_application
from basis.bootstrap import training as execution
from basis.bootstrap.sync import synchronize
from basis.modules.sync.adapters.wire import Conflict as Conflict
from basis.modules.training.public import Unavailable
from basis.shared.identifiers import AccountId

from .models import (
    Block,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekTrip,
)
from .models import (
    SyncReceipt as SyncReceipt,
)


def encode_row(row: models.Model, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        f.name: (
            str(getattr(row, f.attname))
            if isinstance(getattr(row, f.attname), (Decimal, uuid.UUID))
            else cast(object, getattr(row, f.attname))
        )
        for f in row._meta.concrete_fields
        if f.name not in {"id", "block", "order", *exclude}
    }


def session_snapshot(session: Session) -> dict[str, object]:
    return execution.snapshot(session.owner_id, session.pk)


def validate_block_data(data: object) -> None:
    allowed = {"id", "order", "sport", "title", "target", "actual", "notes", "sets", "intervals"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValidationError("Formato de bloque inválido.")
    if (
        not isinstance(data.get("sets", []), list)
        or not isinstance(data.get("intervals", []), list)
        or len(data.get("sets", [])) > 100
        or len(data.get("intervals", [])) > 100
    ):
        raise ValidationError("Demasiadas series o intervalos.")


def save_blocks(parent: Session | PlannedSession, blocks: object) -> None:
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 30:
        raise ValidationError("Una sesión necesita entre 1 y 30 bloques.")
    for index, data in enumerate(blocks, 1):
        validate_block_data(data)
        data = cast(dict[str, object], data)
        block = Block(
            **{k: data[k] for k in ("sport", "title", "target", "actual", "notes") if k in data},
            order=index,
        )
        if isinstance(parent, Session):
            block.session = parent
        else:
            block.planned = parent
        cast(Callable[[], None], block.save)()
        for model, key in ((StrengthSet, "sets"), (Interval, "intervals")):
            allowed = {f.name for f in model._meta.fields} - {"id", "block", "order"}
            for order, row in enumerate(cast(list[object], data.get(key, [])), 1):
                if not isinstance(row, dict) or set(row) - allowed:
                    raise ValidationError("Variables de serie o intervalo inválidas.")
                values = {
                    k + "_id" if k in ("exercise", "rm_reference") else k: v for k, v in row.items()
                }
                for field in model._meta.fields:
                    if (
                        isinstance(field, models.DecimalField)
                        and values.get(field.name) is not None
                    ):
                        values[field.name] = Decimal(str(values[field.name]))
                model.objects.create(block=block, order=order, **values)


def sync_session(
    owner: AbstractBaseUser, mutation_id: object, payload: object
) -> dict[str, object]:
    return synchronize(AccountId(owner.pk), mutation_id, payload)


@transaction.atomic
def start_session(owner: AbstractBaseUser, planned: PlannedSession) -> Session:
    try:
        state = execution.start(owner.pk, planned.pk)
    except Unavailable as exc:
        raise PlannedSession.DoesNotExist(str(exc)) from None
    return Session.objects.get(pk=state.id)


def revise_plan(owner: AbstractBaseUser, plan: TrainingPlan) -> TrainingPlan:
    return planning.revise(owner.pk, plan.pk)


def progress_report(owner: AbstractBaseUser) -> dict[str, object]:
    return progress_application.report(owner.pk)


def trip_summary(trip: TrekTrip) -> dict[str, object]:
    return progress_application.trip_summary(trip.owner_id, trip.pk)
