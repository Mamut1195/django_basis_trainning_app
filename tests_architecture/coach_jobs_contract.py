"""Shared durable-job repository contract for fake and Django adapters."""

from dataclasses import replace
from typing import Callable
from unittest import TestCase

from basis.modules.coach.application.jobs import JobsRepository
from basis.modules.coach.domain.jobs import Job
from basis.shared.identifiers import AccountId
from basis.shared.ports import UnitOfWork


class JobsContract:
    repository: JobsRepository
    owner: AccountId
    other: AccountId
    uow_factory: Callable[[], UnitOfWork]
    sample: Job

    def test_contract_commit_ids_owner_and_rollback(self) -> None:
        assert isinstance(self, TestCase)
        with self.uow_factory() as work:
            self.repository.create(self.sample)
            work.commit()
        found = self.repository.existing(self.owner, self.sample.request_key)
        assert found is not None
        self.assertEqual(found.id, self.sample.id)
        self.assertEqual(found.context, self.sample.context)
        self.assertIsNone(self.repository.existing(self.other, self.sample.request_key))
        with self.uow_factory():
            self.repository.save_job(replace(found, status="failed"))
        self.assertEqual(self.repository.job(found.id).status, "pending")
        with self.assertRaises(ValueError), self.uow_factory() as work:
            self.repository.save_job(replace(found, status="failed"))
            work.commit()
            raise ValueError("rollback even after commit request")
        self.assertEqual(self.repository.job(found.id).status, "pending")

    def test_contract_claim_once_and_stale_never_retries(self) -> None:
        assert isinstance(self, TestCase)
        with self.uow_factory() as work:
            self.repository.create(self.sample)
            work.commit()
        now = self.sample.context.snapshot_at
        with self.uow_factory() as work:
            claimed = self.repository.claim(now)
            work.commit()
        assert claimed is not None
        self.assertEqual(claimed.id, self.sample.id)
        with self.uow_factory() as work:
            self.assertIsNone(self.repository.claim(now))
            self.repository.quarantine(now.replace(year=now.year + 1))
            work.commit()
        self.assertEqual(self.repository.job(self.sample.id).status, "uncertain")
        with self.uow_factory() as work:
            self.assertIsNone(self.repository.claim(now))
            work.commit()
