from django.core.exceptions import ValidationError

from basis.bootstrap.sync import changes, encode_session, synchronization
from basis.modules.sync.adapters.wire import Conflict, WireSource
from basis.modules.sync.public import InvalidSynchronization, SyncCommand
from basis.modules.training.public import (
    ExecutionConflict,
    InvalidExecution,
    Unavailable,
)
from basis.shared.identifiers import AccountId


def synchronize(owner: AccountId, mutation: object, payload: object) -> dict[str, object]:
    try:
        return encode_session(
            synchronization().execute(
                SyncCommand(owner, WireSource(mutation, payload, owner, changes))
            )
        )
    except ExecutionConflict as error:
        raise Conflict(encode_session(error.current)) from None
    except (InvalidSynchronization, Unavailable, InvalidExecution) as error:
        raise ValidationError(str(error)) from None
