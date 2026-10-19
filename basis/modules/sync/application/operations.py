"""Serialize idempotent offline writes without coupling receipt policy to training."""

from dataclasses import dataclass
from typing import Callable, Protocol

from basis.modules.accounts.public import AccountLocks
from basis.modules.training.public import SessionChanges, SessionMutation, SessionState
from basis.shared.identifiers import AccountId, MutationId, Revision
from basis.shared.ports import UnitOfWork

from ..domain.operations import MutationIdentity, Receipt, replay


class SyncSource(Protocol):
    """Boundary conversion is deliberately split around replay and revision guards."""

    def identity(self) -> MutationIdentity: ...
    def revision(self) -> Revision: ...
    def changes(self) -> SessionChanges: ...


class ReceiptRepository(Protocol):
    def get(self, owner: AccountId, mutation: MutationId) -> Receipt | None: ...
    def save(self, receipt: Receipt) -> None: ...


class WriteAuthorization(Protocol):
    def require(self, owner: AccountId) -> None: ...


class SessionRecorder(Protocol):
    def record_from(
        self, command: SessionMutation, source: Callable[[], SessionChanges]
    ) -> SessionState: ...


@dataclass(frozen=True)
class SyncCommand:
    owner: AccountId
    source: SyncSource


class Synchronization:
    def __init__(
        self,
        repository: ReceiptRepository,
        uow: Callable[[], UnitOfWork],
        account_locks: AccountLocks,
        authorization: WriteAuthorization,
        recorder: SessionRecorder,
    ) -> None:
        self.repository = repository
        self.uow = uow
        self.account_locks = account_locks
        self.authorization = authorization
        self.recorder = recorder

    def execute(self, command: SyncCommand) -> SessionState:
        with self.uow() as work:
            self.account_locks.lock(command.owner)
            identity = command.source.identity()
            receipt = self.repository.get(command.owner, identity.mutation)
            if receipt is not None:
                result = replay(receipt, identity.digest)
                work.commit()
                return result
            self.authorization.require(command.owner)
            mutation = SessionMutation(command.owner, identity.session, command.source.revision())
            result = self.recorder.record_from(mutation, command.source.changes)
            self.repository.save(Receipt(command.owner, identity.mutation, identity.digest, result))
            work.commit()
            return result
