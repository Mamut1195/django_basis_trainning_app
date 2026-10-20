"""The manual-write port contract against real Django transactions and HTTP forms."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from basis.bootstrap.transactions import DjangoUnitOfWork
from basis.modules.training.adapters.django import UUIDSessionIds
from basis.modules.training.adapters.manual_repository import DjangoManualRepository
from basis.modules.training.adapters.models import Block, PlannedSession, Session
from basis.modules.training.application.manual import ManualTraining, SaveBlockMetrics
from basis.modules.training.domain.execution import Metric, MetricName
from basis.modules.training.domain.manual import ParentRef, SessionParent
from basis.shared.identifiers import AccountId, BlockId
from tests_architecture.manual_contract import ManualContract
from tests_architecture.test_manual_training import Authorization, References


class DjangoManualContractTests(ManualContract, TestCase):
    def setUp(self) -> None:
        self.owner = AccountId(get_user_model().objects.create_user(username="manual-owner").pk)
        self.other = AccountId(get_user_model().objects.create_user(username="manual-other").pk)
        self.service = ManualTraining(DjangoManualRepository(), DjangoUnitOfWork,
                                      Authorization(), UUIDSessionIds(), References())
        self.counts = lambda: (Session.objects.count(), Block.objects.count())
        self.revision = self.read_revision
        self.first_block = lambda id: BlockId(Block.objects.get(session_id=id).pk)
        self.fail_write = self.inject_failure

    def read_revision(self, ref: ParentRef) -> int:
        if isinstance(ref, SessionParent):
            return Session.objects.get(pk=ref.id).revision
        return PlannedSession.objects.get(pk=ref.id).revision

    def inject_failure(self, operation: str) -> None:
        failure = patch.object(DjangoManualRepository, operation, side_effect=OSError("test persistence failure"))
        failure.start()
        self.addCleanup(failure.stop)

    def test_failure_after_child_sql_rolls_back_both_child_and_parent(self) -> None:
        id = self.create()
        block = self.first_block(id)
        original = DjangoManualRepository.save_metrics

        def fail_after_sql(repository: DjangoManualRepository, block: BlockId,
                           metrics: tuple[Metric, ...], *, actual: bool) -> None:
            original(repository, block, metrics, actual=actual)
            raise OSError("after SQL")

        with patch.object(DjangoManualRepository, "save_metrics", fail_after_sql):
            with self.assertRaises(OSError):
                self.service.save_metrics(SaveBlockMetrics(self.owner, block,
                    self.service.inspect(self.owner, SessionParent(id)).revision,
                    (Metric(MetricName.DURATION_SECONDS, Decimal(0)),)))
        self.assertEqual(self.read_revision(SessionParent(id)), 1)
        self.assertEqual(Block.objects.get(pk=block).actual, {})

    def test_zero_and_absent_session_inputs_remain_distinct_in_storage(self) -> None:
        id = self.create()
        row = Session.objects.get(pk=id)
        self.assertEqual(row.date, date(2026, 1, 1))
        self.assertEqual(row.duration_seconds, 0)
        self.assertEqual(row.reported_rpe, Decimal(0))
        self.assertEqual(Block.objects.get(session_id=id).actual, {})
        self.assertEqual(row.revision, 1)
