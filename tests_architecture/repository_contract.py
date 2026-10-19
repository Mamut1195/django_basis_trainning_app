"""Shared repository/UoW contract, run against fake and Django implementations."""

from typing import Callable

from basis.modules.training.application.execution import SessionRepository
from basis.modules.training.public import SessionState
from basis.shared.ports import UnitOfWork


class RollbackSignal(Exception):
    pass


class RepositoryContract:
    repository: SessionRepository
    make_uow: Callable[[], UnitOfWork]
    initial: SessionState

    def test_contract_no_commit_rolls_back(self) -> None:
        with self.make_uow():
            self.repository.save(self.initial)
        assert self.repository.get(self.initial.id, lock=False) is None

    def test_contract_commit_preserves_identifiers_owner_and_missing_values(self) -> None:
        with self.make_uow() as work:
            self.repository.save(self.initial)
            work.commit()
        restored = self.repository.get(self.initial.id, lock=False)
        assert restored is not None
        assert restored.id == self.initial.id
        assert restored.owner == self.initial.owner
        assert restored.date == self.initial.date
        assert restored.revision == self.initial.revision
        assert restored.reported_rpe is None
        assert restored.duration_seconds is None
        assert restored.blocks[0].actual == self.initial.blocks[0].actual
        assert restored.blocks[0].target == self.initial.blocks[0].target

    def test_contract_exception_rolls_back_even_after_commit_request(self) -> None:
        try:
            with self.make_uow() as work:
                self.repository.save(self.initial)
                work.commit()
                raise RollbackSignal()
        except RollbackSignal:
            pass
        assert self.repository.get(self.initial.id, lock=False) is None

    def test_contract_inner_commit_does_not_escape_outer_rollback(self) -> None:
        with self.make_uow():
            with self.make_uow() as inner:
                self.repository.save(self.initial)
                inner.commit()
        assert self.repository.get(self.initial.id, lock=False) is None
