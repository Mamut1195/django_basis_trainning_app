from datetime import timedelta

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from basis.bootstrap.tests.test_execution import account
from basis.modules.training.adapters.calendar import calendar_status, effective_sessions
from basis.modules.training.adapters.models import (
    Cycle,
    Goal,
    PlannedSession,
    Session,
    TrainingPlan,
)
from basis.modules.training.adapters.progress import DjangoProgressRepository
from basis.shared.identifiers import AccountId


@override_settings(DEVELOPMENT_ACCESS=True)
class QueryBaseline(TestCase):
    def test_query_counts(self) -> None:
        today = timezone.localdate()
        for n in (10, 100, 1000):
            user = account("query-" + str(n))
            owner = AccountId(user.pk)
            goal = Goal.objects.create(owner=user, title="g", sport="running")
            first = TrainingPlan.objects.create(
                owner=user,
                goal=goal,
                title="a",
                start_date=today,
                end_date=today + timedelta(days=1),
            )
            macro = Cycle.objects.create(
                plan=first, title="macro", kind="macro", start_date=today, end_date=today
            )
            meso = Cycle.objects.create(
                plan=first,
                parent=macro,
                title="meso",
                kind="meso",
                start_date=today,
                end_date=today,
            )
            cycle = Cycle.objects.create(
                plan=first,
                parent=meso,
                title="micro",
                kind="micro",
                start_date=today,
                end_date=today,
            )
            TrainingPlan.objects.create(
                owner=user,
                goal=goal,
                title="b",
                start_date=today,
                end_date=today + timedelta(days=1),
                previous=first,
                lineage=first.lineage,
                version=2,
                effective_on=today + timedelta(days=1),
            )
            PlannedSession.objects.bulk_create(
                [
                    PlannedSession(owner=user, plan=first, cycle=cycle, title="s", date=today)
                    for _ in range(n)
                ]
            )
            rows = list(PlannedSession.objects.filter(owner=user).order_by("pk"))
            Session.objects.bulk_create(
                [
                    Session(
                        owner=user,
                        planned=row,
                        title="e",
                        date=today,
                        status="completed" if i % 2 else "in_progress",
                    )
                    for i, row in enumerate(rows)
                ]
            )
            with CaptureQueriesContext(connection) as q:
                selected = effective_sessions(owner)
            selection = len(q)
            with CaptureQueriesContext(connection) as q:
                states = [calendar_status(row, today) for row in selected]
            state_queries = len(q)
            with CaptureQueriesContext(connection) as q:
                due = DjangoProgressRepository().scheduled(owner, today)
            progress = len(q)
            self.client.force_login(user)
            with CaptureQueriesContext(connection) as q:
                response = self.client.get("/")
            assert response.status_code == 200
            assert len(selected) == n and len(due) == n and states.count("Completada") == n // 2
            print(
                f"QUERY_RESULT n={n} selection={selection} statuses={state_queries} scheduled={progress} today={len(q)}"
            )
