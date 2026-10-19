"""Composition root for execution; callers receive the typed public contract."""

from typing import Mapping
from uuid import UUID

from basis.modules.training.adapters.django import (
    DjangoClock,
    DjangoSessionRepository,
    DjangoUnitOfWork,
    DjangoWriteAuthorization,
    UUIDSessionIds,
    session_state,
)
from basis.modules.training.adapters.wire import decode_record, encode_session
from basis.modules.training.public import (
    ReadSession,
    SessionMutation,
    SessionState,
    StartSession,
    Training,
    require_editable,
)
from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId
from training.models import Session


def training() -> Training:
    return Training(
        DjangoSessionRepository(),
        DjangoUnitOfWork,
        DjangoWriteAuthorization(),
        DjangoClock(),
        UUIDSessionIds(),
    )


def start(owner: int, planned: int) -> SessionState:
    return training().start(StartSession(AccountId(owner), PlannedSessionId(planned)))


def snapshot(owner: int, session: UUID) -> dict[str, object]:
    return encode_session(training().read(ReadSession(AccountId(owner), SessionId(session))))


def record(owner: int, payload: Mapping[str, object]) -> dict[str, object]:
    mutation = SessionMutation(
        AccountId(owner),
        SessionId(UUID(str(payload["id"]))),
        Revision(int(str(payload["revision"]))),
    )
    return encode_session(
        training().record_from(mutation, lambda: decode_record(AccountId(owner), payload).changes)
    )


def edit_revision(row: Session, expected: int) -> int:
    current = session_state(row)
    return int(require_editable(current, current.owner, Revision(expected)))
