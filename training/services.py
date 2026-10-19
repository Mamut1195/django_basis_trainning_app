"""Transactional application services shared by web, offline sync and AI proposals."""

import hashlib
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction

from basis.bootstrap import planning
from basis.bootstrap import progress as progress_application
from basis.bootstrap import training as execution
from basis.modules.training.adapters.wire import encode_session
from basis.modules.training.public import ExecutionConflict, InvalidExecution, Unavailable

from .access import require_write_access
from .models import (
    Block,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    SyncReceipt,
)


class Conflict(Exception):
    def __init__(self, current):
        self.current = current


def encode_row(row, exclude=()):
    return {
        f.name: (
            str(getattr(row, f.attname))
            if isinstance(getattr(row, f.attname), (Decimal, uuid.UUID))
            else getattr(row, f.attname)
        )
        for f in row._meta.concrete_fields
        if f.name not in {"id", "block", "order", *exclude}
    }


def session_snapshot(session):
    return execution.snapshot(session.owner_id, session.pk)


def validate_block_data(data):
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


def save_blocks(parent, blocks):
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 30:
        raise ValidationError("Una sesión necesita entre 1 y 30 bloques.")
    for index, data in enumerate(blocks, 1):
        validate_block_data(data)
        block = Block(
            **{k: data[k] for k in ("sport", "title", "target", "actual", "notes") if k in data},
            order=index,
        )
        if isinstance(parent, Session):
            block.session = parent
        else:
            block.planned = parent
        block.save()
        for model, key in ((StrengthSet, "sets"), (Interval, "intervals")):
            allowed = {f.name for f in model._meta.fields} - {"id", "block", "order"}
            for order, row in enumerate(data.get(key, []), 1):
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


@transaction.atomic
def sync_session(owner, mutation_id, payload):
    # Serializes even creation of a new session/idempotency key on PostgreSQL.
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    try:
        mutation_id = uuid.UUID(str(mutation_id))
        uuid.UUID(str(payload["id"]))
    except (ValueError, KeyError, TypeError):
        raise ValidationError("Identificador de sincronización inválido.") from None
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt = SyncReceipt.objects.filter(owner=owner, mutation_id=mutation_id).first()
    if receipt:
        if receipt.payload_hash != digest:
            raise ValidationError("La misma operación no puede contener datos diferentes.")
        return receipt.result
    require_write_access(owner)
    allowed = {
        "id",
        "revision",
        "title",
        "date",
        "status",
        "duration_seconds",
        "duration_protocol",
        "reported_rpe",
        "notes",
        "planned",
        "blocks",
    }
    if set(payload) - allowed or type(payload.get("revision")) is not int:
        raise ValidationError("Formato o revisión de sesión inválida.")
    try:
        result = execution.record(owner.pk, payload)
    except ExecutionConflict as exc:
        raise Conflict(encode_session(exc.current)) from None
    except (Unavailable, InvalidExecution) as exc:
        raise ValidationError(str(exc)) from None
    SyncReceipt.objects.create(
        owner=owner, mutation_id=mutation_id, payload_hash=digest, result=result
    )
    return result


@transaction.atomic
def start_session(owner, planned):
    try:
        state = execution.start(owner.pk, planned.pk)
    except Unavailable as exc:
        raise PlannedSession.DoesNotExist(str(exc)) from None
    return Session.objects.get(pk=state.id)


def revise_plan(owner, plan):
    return planning.revise(owner.pk, plan.pk)


def progress_report(owner):
    return progress_application.report(owner.pk)


def trip_summary(trip):
    return progress_application.trip_summary(trip.owner_id, trip.pk)
