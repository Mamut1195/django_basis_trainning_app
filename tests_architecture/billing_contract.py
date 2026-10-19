"""Identical repository/transaction contract exercised in memory and Django."""

from dataclasses import replace
from typing import Callable
from unittest import TestCase

from basis.modules.billing.application.service import BillingRepository
from basis.shared.identifiers import AccountId
from basis.shared.ports import UnitOfWork


class BillingContract:
    repository: BillingRepository
    owner: AccountId
    other: AccountId
    uow_factory: Callable[[], UnitOfWork]

    def test_contract_commit_and_owner_scope(self) -> None:
        assert isinstance(self, TestCase)
        with self.uow_factory() as uow:
            state = self.repository.lock(self.owner)
            self.repository.save(replace(state, trial_used=True))
            uow.commit()
        saved = self.repository.get(self.owner)
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.owner, self.owner)
        self.assertTrue(saved.trial_used)
        self.assertIsNone(self.repository.get(self.other))

    def test_contract_uncommitted_creation_and_exception_rollback(self) -> None:
        assert isinstance(self, TestCase)
        with self.uow_factory():
            self.repository.lock(self.other)
        self.assertIsNone(self.repository.get(self.other))
        with self.assertRaises(ValueError), self.uow_factory() as uow:
            state = self.repository.lock(self.other)
            self.repository.save(replace(state, trial_used=True))
            uow.commit()
            raise ValueError("rollback even after requested commit")
        self.assertIsNone(self.repository.get(self.other))
