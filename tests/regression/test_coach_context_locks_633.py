"""Real PostgreSQL row waits; no mock can establish these acceptance locks."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from queue import Queue
from threading import Event
from time import monotonic

from django.db import close_old_connections, connections, transaction
from django.db.transaction import TransactionManagementError
from django.test import TransactionTestCase, skipUnlessDBFeature

from basis.adapters.django.account_locks import lock_account
from basis.bootstrap.athletes import athletes
from basis.modules.athletes.adapters.coach import DjangoAthleteCoachContexts
from basis.modules.athletes.adapters.django import DjangoAthleteRecords
from basis.modules.athletes.adapters.models import AthleteSettings, SportProfile
from basis.modules.athletes.public import EditPreferences, EditProfile, RecordSport, SportData
from basis.modules.catalog.adapters.coach import DjangoCoachExercises
from basis.modules.catalog.adapters.models import Exercise
from basis.modules.coach.application.context import Contexts
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.training.adapters.coach import DjangoTrainingCoachContexts
from basis.modules.training.adapters.models import Goal, TrainingPlan
from basis.shared.identifiers import AccountId, ExerciseId, PlanId, SportProfileId
from tests_architecture.test_coach_context_633 import TODAY, Clock

from .factories import account, exercise


@skipUnlessDBFeature("has_select_for_update")
class AcceptanceContextLock633Tests(TransactionTestCase):
    def setUp(self) -> None:
        self.owner = account("locks633")
        self.owner_id = AccountId(self.owner.pk)
        self.exercise = exercise()
        self.sport = SportProfile.objects.create(
            owner=self.owner, sport="running", experience="beginner"
        )
        self.service = Contexts(
            DjangoAthleteCoachContexts(),
            DjangoTrainingCoachContexts(),
            DjangoCoachExercises(),
            Clock(),
        )

    def assert_writer_waits(
        self, writer: Callable[[], None], expected_sql: str, base_plan: PlanId | None = None
    ) -> None:
        """Prove the active statement waits on this backend, then release/finish."""
        pids: Queue[int] = Queue()
        done = Event()

        def write() -> None:
            close_old_connections()
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '12s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(int(cursor.fetchone()[0]))
                writer()
                done.set()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                lock_account(self.owner_id)
                self.service.snapshot_for_acceptance(
                    self.owner_id, "plan", base_plan, exercise_ids=(ExerciseId(self.exercise.pk),)
                )
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    holder = int(cursor.fetchone()[0])
                future = pool.submit(write)
                writer_pid = pids.get(timeout=3)
                blocked_statement = ""
                deadline = monotonic() + 4
                while monotonic() < deadline and not done.is_set():
                    with connections["default"].cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute(
                            "SELECT wait_event_type, query, pg_blocking_pids(pid) "
                            "FROM pg_stat_activity WHERE pid = %s",
                            [writer_pid],
                        )
                        row = cursor.fetchone()
                    if row is not None and row[0] == "Lock" and holder in row[2]:
                        blocked_statement = str(row[1])
                        break
                    done.wait(0.01)
                self.assertIn(expected_sql, blocked_statement)
                self.assertFalse(done.is_set())
            # The writer must finish after the outer acceptance transaction ends.
            future.result(timeout=10)
        self.assertTrue(done.is_set())

    def test_official_free_preferences_update_waits_on_settings_row(self) -> None:
        data = replace(DjangoAthleteRecords().preferences(self.owner_id), minutes_per_session=45)

        def write() -> None:
            athletes().edit_preferences(EditPreferences(self.owner_id, data))

        self.assert_writer_waits(write, 'UPDATE "basis_athletes_athletesettings"')
        self.assertEqual(AthleteSettings.objects.get(owner=self.owner).minutes_per_session, 45)

    def test_official_profile_edit_waits_on_profile_anchor(self) -> None:
        data = replace(
            DjangoAthleteRecords().profile(self.owner_id), objetivos="Updated after acceptance"
        )

        def write() -> None:
            athletes().edit_profile(EditProfile(self.owner_id, data))

        self.assert_writer_waits(write, '"basis_athletes_user"')
        self.assertEqual(DjangoAthleteRecords().profile(self.owner_id).objetivos, data.objetivos)

    def test_official_sport_insert_waits_on_profile_anchor(self) -> None:
        def write() -> None:
            athletes().record_sport(
                RecordSport(
                    self.owner_id,
                    SportData("cycling", "beginner", None, "", None, ""),
                )
            )

        self.assert_writer_waits(write, '"basis_athletes_user"')
        self.assertTrue(SportProfile.objects.filter(owner=self.owner, sport="cycling").exists())

    def test_official_sport_edit_waits_on_profile_anchor(self) -> None:
        def write() -> None:
            athletes().record_sport(
                RecordSport(
                    self.owner_id,
                    SportData("running", "intermediate", None, "", None, ""),
                    SportProfileId(self.sport.pk),
                )
            )

        self.assert_writer_waits(write, '"basis_athletes_user"')
        self.sport.refresh_from_db()
        self.assertEqual(self.sport.experience, "intermediate")

    def test_existing_sport_row_itself_is_locked(self) -> None:
        def write() -> None:
            SportProfile.objects.filter(pk=self.sport.pk).update(experience="intermediate")

        self.assert_writer_waits(write, 'UPDATE "basis_athletes_sportprofile"')

    def test_referenced_catalog_update_waits_on_exercise_row(self) -> None:
        def write() -> None:
            Exercise.objects.filter(pk=self.exercise.pk).update(nombre="Changed after acceptance")

        self.assert_writer_waits(write, 'UPDATE "basis_catalog_exercise"')

    def test_projected_goal_update_waits_on_goal_row(self) -> None:
        goal = Goal.objects.create(owner=self.owner, sport="running", title="Synthetic")

        def write() -> None:
            Goal.objects.filter(pk=goal.pk).update(title="Changed after acceptance")

        self.assert_writer_waits(write, 'UPDATE "basis_training_goal"')

    def test_selected_base_update_waits_on_plan_row(self) -> None:
        goal = Goal.objects.create(owner=self.owner, sport="running", title="Synthetic")
        plan = TrainingPlan.objects.create(
            owner=self.owner, goal=goal, title="Synthetic", start_date=TODAY, end_date=TODAY
        )

        def write() -> None:
            TrainingPlan.objects.filter(pk=plan.pk).update(title="Changed after acceptance")

        self.assert_writer_waits(write, 'UPDATE "basis_training_trainingplan"', PlanId(plan.pk))

    def test_unreferenced_catalog_rows_remain_writable(self) -> None:
        other = Exercise.objects.create(
            classification=self.exercise.classification, nombre="Unreferenced"
        )

        def write() -> None:
            close_old_connections()
            try:
                Exercise.objects.filter(pk=other.pk).update(nombre="Unreferenced changed")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                lock_account(self.owner_id)
                self.service.snapshot_for_acceptance(
                    self.owner_id, "plan", None, exercise_ids=(ExerciseId(self.exercise.pk),)
                )
                pool.submit(write).result(timeout=3)
        other.refresh_from_db()
        self.assertEqual(other.nombre, "Unreferenced changed")

    def test_normal_snapshot_does_not_block_preferences_updates(self) -> None:
        def write() -> None:
            close_old_connections()
            try:
                AthleteSettings.objects.filter(owner=self.owner).update(minutes_per_session=46)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                self.service.snapshot(self.owner_id, "plan", None)
                pool.submit(write).result(timeout=3)
        self.assertEqual(AthleteSettings.objects.get(owner=self.owner).minutes_per_session, 46)

    def test_locking_ports_require_uow_and_absent_preferences_prevent_acceptance(self) -> None:
        with self.assertRaises(TransactionManagementError):
            DjangoAthleteCoachContexts().read_for_acceptance(self.owner_id)
        with self.assertRaises(TransactionManagementError):
            DjangoTrainingCoachContexts().read_for_acceptance(self.owner_id, TODAY, None)
        with self.assertRaises(TransactionManagementError):
            DjangoCoachExercises().read_for_acceptance((ExerciseId(self.exercise.pk),))
        AthleteSettings.objects.filter(owner=self.owner).delete()
        self.assertIsNone(self.service.snapshot(self.owner_id, "plan", None).athlete.preferences)
        with transaction.atomic():
            lock_account(self.owner_id)
            with self.assertRaisesRegex(CoachInvalid, "preferencias"):
                self.service.snapshot_for_acceptance(self.owner_id, "plan", None)
        self.assertFalse(AthleteSettings.objects.filter(owner=self.owner).exists())

    def test_missing_referenced_exercise_fails_closed(self) -> None:
        with transaction.atomic():
            lock_account(self.owner_id)
            with self.assertRaises(CoachInvalid):
                self.service.snapshot_for_acceptance(
                    self.owner_id, "plan", None, exercise_ids=(ExerciseId(999999),)
                )
