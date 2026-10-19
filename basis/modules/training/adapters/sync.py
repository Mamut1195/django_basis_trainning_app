"""Decode immutable receipt snapshots without consulting current persistence."""

from dataclasses import replace
from uuid import UUID

from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId

from ..public import DurationProtocol, SessionState, SessionStatus
from .wire import (
    blocks,
    day,
    integer,
    object_map,
    optional_decimal,
    optional_integer,
    sequence,
    text,
)


def decode_snapshot(owner: AccountId, raw: object) -> SessionState:
    row = object_map(raw)
    raw_blocks = sequence(row["blocks"])
    restored = blocks(raw_blocks)
    preserved = tuple(
        replace(block, id=optional_integer(object_map(raw_block)["id"]),
                order=integer(object_map(raw_block)["order"]))
        for block, raw_block in zip(restored, raw_blocks, strict=True)
    )
    planned = optional_integer(row["planned"])
    return SessionState(
        id=SessionId(UUID(text(row["id"]))), owner=owner,
        revision=Revision(integer(row["revision"])), date=day(row["date"]),
        title=text(row["title"]), status=SessionStatus(text(row["status"])),
        duration_seconds=optional_integer(row["duration_seconds"]),
        duration_protocol=DurationProtocol(text(row["duration_protocol"])),
        reported_rpe=optional_decimal(row["reported_rpe"]), notes=text(row["notes"]),
        planned=PlannedSessionId(planned) if planned is not None else None, blocks=preserved,
    )
