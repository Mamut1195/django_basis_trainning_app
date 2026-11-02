"""Read-only application probes against disposable data and fake providers."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from basis.bootstrap.tests.test_execution import account
from basis.modules.training.adapters.calendar import calendar_status
from basis.modules.training.adapters.models import Cycle, Goal, PlannedSession, TrainingPlan
from tests_architecture.test_coach_jobs import JobsTests


class AuditProbes(TestCase):
    def test_historical_status_query_growth(self) -> None:
        day = timezone.localdate()
        for n in (10, 100):
            user = account(f"audit-history-{n}")
            goal = Goal.objects.create(owner=user, title="g", sport="running")
            plan = TrainingPlan.objects.create(
                owner=user, goal=goal, title="old", start_date=day, end_date=day + timedelta(days=1)
            )
            cycle = Cycle.objects.create(
                plan=plan, title="m", kind="macro", start_date=day, end_date=day
            )
            TrainingPlan.objects.create(
                owner=user,
                goal=goal,
                title="new",
                start_date=day,
                end_date=day + timedelta(days=1),
                previous=plan,
                lineage=plan.lineage,
                version=2,
                effective_on=day,
            )
            PlannedSession.objects.bulk_create(
                [
                    PlannedSession(owner=user, plan=plan, cycle=cycle, title="s", date=day)
                    for _ in range(n)
                ]
            )
            # Exact historical selection/status path in plan_detail, excluding other view queries.
            with CaptureQueriesContext(connection) as queries:
                rows = list(plan.sessions.all())
                statuses = [calendar_status(row, day) for row in rows]
            self.assertEqual(len(statuses), n)
            self.assertEqual(len(queries), 1 + 2 * n)
            print(f"AUDIT historical_rows={n} selection_and_status_queries={len(queries)}")

    def test_reported_model_not_validated(self) -> None:
        fixture = JobsTests()
        fixture.setUp()
        job = fixture.service.enqueue(fixture.command())
        fixture.service.process_one()
        result = fixture.memory.job(job.id)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.reported_model, "reported")
        self.assertFalse(fixture.memory.blocked())
        print(
            f"AUDIT requested={result.requested_model} reported={result.reported_model} "
            f"status={result.status} cost={result.cost}"
        )

    def test_pending_job_uses_current_not_frozen_rate(self) -> None:
        costs = []
        for rate in (Decimal("0.30") / 1000000, Decimal("0.60") / 1000000):
            fixture = JobsTests()
            fixture.setUp()
            job = fixture.service.enqueue(fixture.command())
            with patch("basis.modules.coach.domain.jobs.INPUT_RATE", rate):
                fixture.service.process_one()
            costs.append(fixture.memory.job(job.id).cost)
        self.assertEqual(costs, [Decimal("0.00036120"), Decimal("0.00060120")])
        print(f"AUDIT same_queued_job_usage costs_before_after_rate_change={costs}")
