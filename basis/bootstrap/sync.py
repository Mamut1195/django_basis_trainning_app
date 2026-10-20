"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.bootstrap.billing import write_authorization
from basis.bootstrap.training import training
from basis.modules.accounts.adapters.coach import DjangoAccountLocks
from basis.modules.sync.adapters.receipts import DjangoReceiptRepository
from basis.modules.sync.public import Synchronization
from basis.modules.training.adapters.execution_actions import changes as changes
from basis.modules.training.adapters.sync import decode_snapshot as decode_snapshot
from basis.modules.training.adapters.wire import encode_session as encode_session


def synchronization() -> Synchronization:
    return Synchronization(
        DjangoReceiptRepository(decode_snapshot, encode_session),
        DjangoUnitOfWork,
        DjangoAccountLocks(),
        write_authorization(),
        training(),
    )
