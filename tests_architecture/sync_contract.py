"""Receipt persistence contract shared by memory and Django adapters."""

from typing import Callable

from basis.modules.sync.application.operations import ReceiptRepository
from basis.modules.sync.domain.operations import Receipt
from basis.shared.identifiers import AccountId
from basis.shared.ports import UnitOfWork


class ReceiptContract:
    repository: ReceiptRepository
    make_uow: Callable[[], UnitOfWork]
    initial: Receipt

    def test_receipt_commit_preserves_frozen_snapshot(self) -> None:
        with self.make_uow() as work:
            self.repository.save(self.initial)
            work.commit()
        restored = self.repository.get(self.initial.owner, self.initial.mutation)
        assert restored == self.initial
        assert restored.result.blocks[0].id == 41
        assert restored.result.duration_seconds == 0
        assert restored.result.reported_rpe is None

    def test_receipt_no_commit_rolls_back(self) -> None:
        with self.make_uow():
            self.repository.save(self.initial)
        assert self.repository.get(self.initial.owner, self.initial.mutation) is None

    def test_receipt_exception_after_commit_rolls_back(self) -> None:
        try:
            with self.make_uow() as work:
                self.repository.save(self.initial)
                work.commit()
                raise RuntimeError("rollback")
        except RuntimeError:
            pass
        assert self.repository.get(self.initial.owner, self.initial.mutation) is None

    def test_receipt_owner_isolation(self) -> None:
        with self.make_uow() as work:
            self.repository.save(self.initial)
            work.commit()
        assert (
            self.repository.get(AccountId(self.initial.owner + 1000), self.initial.mutation) is None
        )

    def test_receipt_inner_commit_does_not_escape_outer_rollback(self) -> None:
        with self.make_uow():
            with self.make_uow() as inner:
                self.repository.save(self.initial)
                inner.commit()
        assert self.repository.get(self.initial.owner, self.initial.mutation) is None
