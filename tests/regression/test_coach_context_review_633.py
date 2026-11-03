"""Review P1/P2 regressions: real inverse-order PG waits and captured owner dates."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections, connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import PermissionDenied

from basis.adapters.django.account_locks import lock_account
from basis.adapters.django.transactions import DjangoClock
from basis.bootstrap.athletes import athletes, personal_authorization
from basis.modules.athletes.adapters.coach import DjangoAthleteCoachContexts
from basis.modules.athletes.adapters.django import DjangoAthleteRecords
from basis.modules.athletes.adapters.models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    Wellness,
)
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.public import EditPreferences, EditProfile, RecordSport, SportData
from basis.modules.catalog.adapters.coach import DjangoCoachExercises
from basis.modules.coach.application.context import Contexts
from basis.modules.training.adapters.coach import DjangoTrainingCoachContexts
from basis.modules.training.adapters.models import Session
from basis.shared.identifiers import AccountId, SportProfileId
from tests_architecture.test_coach_context_633 import Clock

from .factories import account


def service(clock: Clock | DjangoClock) -> Contexts:
    return Contexts(
        DjangoAthleteCoachContexts(), DjangoTrainingCoachContexts(), DjangoCoachExercises(), clock
    )


@skipUnlessDBFeature("has_select_for_update")
class PersonalWriterOrder633Tests(TransactionTestCase):
    def setUp(self) -> None:
        # Personal access is free: these operations must work with canceled billing.
        self.owner = account("review633", status="canceled")
        self.owner_id = AccountId(self.owner.pk)
        Athlete.objects.filter(account_id=self.owner_id).update(peso=Decimal(70))
        self.sport = SportProfile.objects.create(owner=self.owner, sport="running")

    def write(self, operation: str) -> None:
        records = DjangoAthleteRecords()
        if operation == "preferences":
            data = replace(records.preferences(self.owner_id), minutes_per_session=47)
            athletes().edit_preferences(EditPreferences(self.owner_id, data))
        elif operation == "profile_archive":
            profile_data = replace(records.profile(self.owner_id), peso=Decimal(71))
            athletes().edit_profile(EditProfile(self.owner_id, profile_data))
        elif operation == "sport_insert":
            athletes().record_sport(
                RecordSport(
                    self.owner_id,
                    SportData("cycling", "beginner", None, "", None, ""),
                )
            )
        else:
            athletes().record_sport(
                RecordSport(
                    self.owner_id,
                    SportData("running", "intermediate", None, "", None, ""),
                    SportProfileId(self.sport.pk),
                )
            )

    def wait_state(self, pid: int) -> tuple[tuple[int, ...], str]:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute(
                "SELECT pg_blocking_pids(pid), query FROM pg_stat_activity WHERE pid=%s", [pid]
            )
            row = cursor.fetchone()
        return (tuple(int(n) for n in row[0]), str(row[1])) if row else ((), "")

    def exercise_order(self, operation: str, writer_first: bool) -> None:
        first_ready = Barrier(2)
        release_first = Event()
        pids: Queue[tuple[str, int]] = Queue()

        def run(actor: str, first: bool) -> str | None:
            close_old_connections()
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET lock_timeout='8s'")
                    cursor.execute("SET statement_timeout='12s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put((actor, int(cursor.fetchone()[0])))
                with transaction.atomic():
                    if actor == "writer":
                        self.write(operation)
                    else:
                        lock_account(self.owner_id)
                        service(Clock()).snapshot_for_acceptance(self.owner_id, "plan", None)
                    if first:
                        first_ready.wait(timeout=6)
                        if not release_first.wait(timeout=6):
                            raise TimeoutError("review633 gate timed out")
                return None
            except DatabaseError as error:
                return str(
                    getattr(error.__cause__, "sqlstate", None)
                    or getattr(error.__cause__, "pgcode", None)
                    or type(error).__name__
                )
            finally:
                connections.close_all()

        first_actor, second_actor = (
            ("writer", "acceptance") if writer_first else ("acceptance", "writer")
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, first_actor, True)
            first_pid = pids.get(timeout=3)[1]
            first_ready.wait(timeout=6)
            second = pool.submit(run, second_actor, False)
            second_pid = pids.get(timeout=3)[1]
            observed = False
            statement = ""
            try:
                deadline = monotonic() + 4
                while monotonic() < deadline:
                    blockers, statement = self.wait_state(second_pid)
                    if first_pid in blockers:
                        observed = True
                        break
                    if second.done():
                        break
                    Event().wait(0.01)
            finally:
                release_first.set()
            cycle = False
            cycle_queries: tuple[str, str] | None = None
            deadline = monotonic() + 3
            while monotonic() < deadline and not (first.done() and second.done()):
                first_blockers, first_query = self.wait_state(first_pid)
                second_blockers, second_query = self.wait_state(second_pid)
                if second_pid in first_blockers and first_pid in second_blockers:
                    cycle = True
                    cycle_queries = (first_query[:240], second_query[:240])
                Event().wait(0.01)
            errors = [first.result(timeout=12), second.result(timeout=12)]
        print(
            "REVIEW633_ORDER "
            + json.dumps(
                {
                    "operation": operation,
                    "writer_first": writer_first,
                    "first_pid": first_pid,
                    "second_pid": second_pid,
                    "second_waits_for_first": observed,
                    "cycle_observed": cycle,
                    "cycle_queries": cycle_queries,
                    "contended_statement": statement[:240],
                    "sqlstates": errors,
                }
            )
        )
        self.assertTrue(observed, "Second operation did not demonstrably wait for first")
        self.assertEqual(
            errors,
            [None, None],
            "Official writes and acceptance must both terminate without deadlock",
        )
        self.assertFalse(cycle)
        self.assertTrue(
            '"auth_user"' in statement and "FOR UPDATE" in statement,
            "First contended statement must lock the account, before aggregate rows",
        )

    def test_writer_first_then_acceptance(self) -> None:
        for operation in ("sport_insert", "profile_archive", "preferences", "sport_edit"):
            with self.subTest(operation=operation):
                self.exercise_order(operation, True)
        self.assertEqual(
            Measurement.objects.filter(owner=self.owner, origin="legacy_profile").count(), 1
        )

    def test_acceptance_first_then_writer(self) -> None:
        for operation in ("sport_insert", "profile_archive", "preferences", "sport_edit"):
            with self.subTest(operation=operation):
                self.exercise_order(operation, False)
        self.assertEqual(
            Measurement.objects.filter(owner=self.owner, origin="legacy_profile").count(), 1
        )

    def test_autocommit_free_preflight_and_personal_policy_are_preserved(self) -> None:
        self.assertFalse(connections["default"].in_atomic_block)
        with CaptureQueriesContext(connections["default"]) as queries:
            personal_authorization().require(self.owner_id)
        self.assertFalse(any("FOR UPDATE" in q["sql"] for q in queries))
        with transaction.atomic(), CaptureQueriesContext(connections["default"]) as queries:
            personal_authorization().require(self.owner_id)
        self.assertTrue(
            any('FROM "auth_user"' in q["sql"] and "FOR UPDATE" in q["sql"] for q in queries)
        )
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            personal_authorization().require(self.owner_id)
        self.owner.is_active = True
        self.owner.save(update_fields=["is_active"])
        Athlete.objects.filter(account_id=self.owner_id).update(email_verified=False)
        with self.assertRaises(PermissionDenied):
            personal_authorization().require(self.owner_id)
        with self.assertRaises(PermissionDenied):
            personal_authorization().require(AccountId(999999))


class OwnerDateReview633Tests(TestCase):
    def test_captured_django_instant_uses_owner_today_for_sessions_and_wellness(self) -> None:
        for zone, instant, expected in (
            ("Asia/Tokyo", datetime(2026, 11, 2, 2, 30, tzinfo=timezone.utc), date(2026, 11, 2)),
            (
                "Pacific/Honolulu",
                datetime(2026, 11, 2, 7, 30, tzinfo=timezone.utc),
                date(2026, 11, 1),
            ),
        ):
            with self.subTest(zone=zone):
                owner = account("date633-" + zone.replace("/", "-"))
                AthleteSettings.objects.filter(owner=owner).update(timezone_name=zone)
                current = Session.objects.create(
                    owner=owner, date=expected, title="Owner today", status="completed"
                )
                boundary = Session.objects.create(
                    owner=owner,
                    date=expected - timedelta(days=13),
                    title="Boundary",
                    status="completed",
                )
                Session.objects.create(
                    owner=owner, date=expected + timedelta(days=1), title="Future"
                )
                Session.objects.create(
                    owner=owner, date=expected - timedelta(days=14), title="Too old"
                )
                wellness = Wellness.objects.create(owner=owner, date=expected, sleep_hours=0)
                with patch(
                    "basis.adapters.django.transactions.timezone.now", return_value=instant
                ) as now:
                    context = service(DjangoClock()).snapshot(AccountId(owner.pk), "short", None)
                print(
                    "REVIEW633_DATE "
                    + json.dumps(
                        {
                            "zone": zone,
                            "instant": instant.isoformat(),
                            "expected": expected.isoformat(),
                            "actual_end": str(context.training.scope.end)
                            if context.training.scope
                            else None,
                            "wellness": str(context.athlete.wellness.date)
                            if context.athlete.wellness
                            else None,
                            "now_calls": now.call_count,
                        }
                    )
                )
                self.assertEqual(context.snapshot_at, instant)
                assert context.training.scope is not None
                self.assertEqual(context.training.scope.end, expected)
                self.assertEqual(now.call_count, 1)
                self.assertEqual(
                    [s.id for s in context.training.recent], [str(current.pk), str(boundary.pk)]
                )
                assert context.athlete.wellness is not None
                self.assertEqual(context.athlete.wellness.date, expected)
                with transaction.atomic():
                    lock_account(AccountId(owner.pk))
                    with (
                        CaptureQueriesContext(connections["default"]) as queries,
                        patch(
                            "basis.adapters.django.transactions.timezone.now", return_value=instant
                        ) as now,
                    ):
                        locked = service(DjangoClock()).snapshot_for_acceptance(
                            AccountId(owner.pk), "plan", None
                        )
                    self.assertEqual(now.call_count, 1)
                    self.assertTrue(
                        any(
                            '"basis_athletes_athletesettings"' in q["sql"]
                            and "FOR UPDATE" in q["sql"]
                            for q in queries
                        )
                    )
                    self.assertEqual(locked.training.scope, context.training.scope)
                    self.assertEqual(locked.athlete.wellness, context.athlete.wellness)
                for offset in (-14, 1):
                    # Administrative corruption/staleness is not current evidence.
                    Wellness.objects.filter(pk=wellness.pk).update(
                        date=expected + timedelta(days=offset)
                    )
                    with patch(
                        "basis.adapters.django.transactions.timezone.now", return_value=instant
                    ):
                        absent = service(DjangoClock()).snapshot(AccountId(owner.pk), "short", None)
                    self.assertIsNone(absent.athlete.wellness)
                    self.assertIn("wellness_in_period", absent.missing)
