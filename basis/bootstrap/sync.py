"""Explicit composition of offline receipts, account locks and training execution."""

from collections.abc import Mapping

from django.core.exceptions import ValidationError

from basis.bootstrap.billing import write_authorization
from basis.bootstrap.training import training
from basis.bootstrap.transactions import DjangoUnitOfWork
from basis.modules.accounts.adapters.coach import DjangoAccountLocks
from basis.modules.sync.adapters.receipts import DjangoReceiptRepository
from basis.modules.sync.adapters.wire import Conflict, WireSource
from basis.modules.sync.public import InvalidSynchronization, SyncCommand, Synchronization
from basis.modules.training.adapters.sync import decode_snapshot as decode_snapshot
from basis.modules.training.adapters.wire import decode_record
from basis.modules.training.adapters.wire import encode_session as encode_session
from basis.modules.training.public import (
    ExecutionConflict,
    InvalidExecution,
    SessionChanges,
    Unavailable,
)
from basis.shared.identifiers import AccountId


def synchronization() -> Synchronization:
    return Synchronization(
        DjangoReceiptRepository(decode_snapshot, encode_session), DjangoUnitOfWork,
        DjangoAccountLocks(), write_authorization(), training(),
    )


def changes(owner: AccountId, payload: Mapping[str, object]) -> SessionChanges:
    return decode_record(owner, payload).changes


def synchronize(owner: AccountId, mutation: object, payload: object) -> dict[str, object]:
    try:
        return encode_session(synchronization().execute(
            SyncCommand(owner, WireSource(mutation, payload, owner, changes))
        ))
    except ExecutionConflict as error:
        raise Conflict(encode_session(error.current)) from None
    except (InvalidSynchronization, Unavailable, InvalidExecution) as error:
        raise ValidationError(str(error)) from None
