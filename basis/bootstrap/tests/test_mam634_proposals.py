"""MAM-634: deterministic proposals on the isolated PostgreSQL database, no provider."""

import copy
import json
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from typing import Callable
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from basis.bootstrap.coach import contexts, proposal_decoder, proposals
from basis.bootstrap.planning import planning
from basis.modules.athletes.adapters.models import AthleteSettings
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.coach.adapters.context_wire import encode_context
from basis.modules.coach.adapters.jobs import job_state
from basis.modules.coach.adapters.models import AIJob, PlanProposal, UsagePeriod
from basis.modules.coach.adapters.proposal_actions import (
    accept_proposal,
    edit_and_accept_proposal,
    reject_proposal,
)
from basis.modules.coach.adapters.proposals import (
    DjangoProposalRepository,
    DjangoProposalSink,
    review_key,
)
from basis.modules.coach.adapters.web.forms import ProposalReviewForm
from basis.modules.coach.application.proposals import CreateProposal
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.coach.domain.proposals import Proposal
from basis.modules.training.adapters.coach import DjangoCoachPlanning
from basis.modules.training.adapters.models import (
    Block,
    Goal,
    PlannedSession,
    Session,
    TrainingPlan,
)
from basis.modules.training.public import InvalidPlanning, PlanDefinition, RestorePlan, RevisePlan
from basis.shared.identifiers import AccountId, JobId, PlanId


def account(name: str) -> User:
    user = get_user_model().objects.create_user(username=name, email=name + "@example.test")
    Athlete.objects.create(
        account=user,
        nombre=name,
        email=user.email,
        edad=30,
        fecha_inicio=timezone.localdate(),
        email_verified=True,
    )
    AthleteSettings.objects.create(
        owner=user, availability=[1, 3, 5], equipment="Zapatillas", minutes_per_session=60
    )
    BillingAccount.objects.create(
        owner=user,
        status="active",
        period_start=timezone.now() - timedelta(days=1),
        period_end=timezone.now() + timedelta(days=30),
    )
    return user


def source(goal: Goal) -> dict[str, object]:
    # Monday is explicit, independent of the day on which the suite executes.
    start = date(2027, 1, 4)
    end = start + timedelta(days=6)
    return {
        "title": "Semana propuesta",
        "goal_id": goal.pk,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "notes": "Practicar constancia con poco historial; revisar intensidad con el atleta.",
        "cycles": [
            {
                "key": kind,
                "parent": parent,
                "kind": kind,
                "title": kind,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
            for kind, parent in (("macro", None), ("meso", "macro"), ("micro", "meso"))
        ],
        "sessions": [
            {
                "title": "Carrera suave",
                "date": start.isoformat(),
                "cycle_key": "micro",
                "blocks": [
                    {"sport": "running", "title": "Suave", "target": {"duration_seconds": 1800}}
                ],
            }
        ],
    }


def job_for(owner: User, base: TrainingPlan | None = None) -> AIJob:
    usage, _ = UsagePeriod.objects.get_or_create(owner=owner, key="mam634-synthetic")
    frozen = contexts().snapshot(AccountId(owner.pk), "plan", PlanId(base.pk) if base else None)
    return AIJob.objects.create(
        owner=owner,
        usage_period=usage,
        kind="plan",
        prompt="Fixture local, sin IA real",
        context=encode_context(frozen),
        reservation=Decimal(0),
        requested_model="fixture-not-live",
        base_plan=base,
    )


def draft(
    owner: User, content: dict[str, object], base: TrainingPlan | None = None
) -> PlanProposal:
    job = job_for(owner, base)
    pk = proposals(content).create(
        CreateProposal(
            AccountId(owner.pk),
            JobId(job.pk),
            proposal_decoder()(content),
            PlanId(base.pk) if base else None,
        )
    )
    return PlanProposal.objects.get(pk=pk)


class ProposalBoundary634Tests(TestCase):
    def setUp(self) -> None:
        self.owner = account("mam634")
        self.goal = Goal.objects.create(owner=self.owner, title="Constancia", sport="running")
        self.content = source(self.goal)

    def test_goal_absent_from_authorized_source_is_not_a_proposal(self) -> None:
        job = job_for(self.owner)
        late_goal = Goal.objects.create(owner=self.owner, title="Nuevo", sport="cycling")
        content = source(late_goal)
        with self.assertRaises(CoachInvalid):
            proposals(content).create(
                CreateProposal(
                    AccountId(self.owner.pk), JobId(job.pk), proposal_decoder()(content), None
                )
            )
        self.assertFalse(PlanProposal.objects.exists())
        self.assertFalse(TrainingPlan.objects.exists())

    def test_availability_changed_after_draft_cannot_be_applied(self) -> None:
        row = draft(self.owner, self.content)
        preferences = AthleteSettings.objects.get(owner=self.owner)
        preferences.availability = [2, 4]
        preferences.save()
        with self.assertRaises(ValidationError):
            accept_proposal(self.owner, row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")
        self.assertFalse(TrainingPlan.objects.exists())

    def test_reviewed_reject_after_accept_reports_conflict_but_legacy_reject_is_noop(self) -> None:
        row = draft(self.owner, self.content)
        accepted = accept_proposal(self.owner, row.pk)
        with self.assertRaises(ValidationError):
            reject_proposal(self.owner, row.pk, review_key(row))
        reject_proposal(self.owner, row.pk)
        self.assertEqual(accept_proposal(self.owner, row.pk).pk, accepted.pk)

    def test_edit_failure_does_not_change_source(self) -> None:
        row = draft(self.owner, self.content)
        changed = copy.deepcopy(self.content)
        changed["goal_id"] = 999999
        with self.assertRaises(ValidationError):
            edit_and_accept_proposal(self.owner, row.pk, changed)
        row.refresh_from_db()
        self.assertEqual(row.content, self.content)
        self.assertEqual(row.status, "pending")
        self.assertFalse(TrainingPlan.objects.exists())

    def test_sink_creates_valid_draft_without_calendar_then_acceptance_revalidates(self) -> None:
        job = job_for(self.owner)
        typed = replace(job_state(job), answer=json.dumps(self.content))
        sink = DjangoProposalSink(proposals, proposal_decoder())
        self.assertTrue(sink.complete(typed))
        row = PlanProposal.objects.get(job=job)
        self.assertEqual(row.content, self.content)
        self.assertFalse(TrainingPlan.objects.exists())
        self.assertFalse(PlannedSession.objects.exists())
        preferences = AthleteSettings.objects.get(owner=self.owner)
        preferences.equipment = "Solo calzado; sin bicicleta"
        preferences.save()
        with self.assertRaises(ValidationError):
            accept_proposal(self.owner, row.pk)
        self.assertFalse(TrainingPlan.objects.exists())

    def test_sink_incompatible_calendar_never_exposes_a_draft(self) -> None:
        job = job_for(self.owner)
        content = copy.deepcopy(self.content)
        content["sessions"] = [
            {
                "title": "Martes",
                "date": "2027-01-05",
                "cycle_key": "micro",
                "blocks": [
                    {"sport": "running", "title": "Suave", "target": {"duration_seconds": 1800}}
                ],
            }
        ]
        sink = DjangoProposalSink(proposals, proposal_decoder())
        self.assertFalse(sink.complete(replace(job_state(job), answer=json.dumps(content))))
        self.assertFalse(PlanProposal.objects.exists())
        self.assertFalse(TrainingPlan.objects.exists())

    def test_replay_and_reject_do_not_revalidate_changed_profile_or_corrupt_old_content(
        self,
    ) -> None:
        row = draft(self.owner, self.content)
        result = accept_proposal(self.owner, row.pk)
        preferences = AthleteSettings.objects.get(owner=self.owner)
        preferences.availability = [2]
        preferences.save()
        PlanProposal.objects.filter(pk=row.pk).update(content={"malformed": True})
        self.assertEqual(accept_proposal(self.owner, row.pk).pk, result.pk)
        reject_proposal(self.owner, row.pk)
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_reject_malformed_pending_is_idempotent_and_ignores_changed_profile(self) -> None:
        row = draft(self.owner, self.content)
        PlanProposal.objects.filter(pk=row.pk).update(content={"bad": True})
        preferences = AthleteSettings.objects.get(owner=self.owner)
        preferences.equipment = "Cambiado"
        preferences.save()
        reject_proposal(self.owner, row.pk)
        reject_proposal(self.owner, row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, "rejected")
        self.assertEqual(row.content, {"bad": True})
        self.assertFalse(TrainingPlan.objects.exists())

    def test_changed_profile_preferences_and_goal_each_block_application(self) -> None:
        for field, value in (
            ("equipment", "Sin equipo"),
            ("limitations", "Texto actualizado"),
            ("minutes_per_session", 20),
        ):
            with self.subTest(field=field):
                row = draft(self.owner, self.content)
                preferences = AthleteSettings.objects.get(owner=self.owner)
                previous = getattr(preferences, field)
                setattr(preferences, field, value)
                preferences.save()
                with self.assertRaises(ValidationError):
                    edit_and_accept_proposal(self.owner, row.pk, self.content)
                setattr(preferences, field, previous)
                preferences.save()
        row = draft(self.owner, self.content)
        profile = Athlete.objects.get(account=self.owner)
        profile.objetivos = "Objetivo actualizado"
        profile.save()
        with self.assertRaises(ValidationError):
            accept_proposal(self.owner, row.pk)
        profile.objetivos = None
        profile.save()
        self.goal.title = "Meta actualizada"
        self.goal.save()
        with self.assertRaises(ValidationError):
            accept_proposal(self.owner, row.pk)
        self.assertFalse(TrainingPlan.objects.exists())

    def test_missing_preferences_and_explicit_duration_over_limit_are_blocked(self) -> None:
        preferences = AthleteSettings.objects.get(owner=self.owner)
        preferences.minutes_per_session = 20
        preferences.save()
        with self.assertRaises(CoachInvalid):
            draft(self.owner, self.content)
        preferences.delete()
        with self.assertRaises(CoachInvalid):
            draft(self.owner, self.content)
        self.assertFalse(PlanProposal.objects.exists())

    def test_foreign_source_job_or_changed_base_cannot_be_used(self) -> None:
        other = account("mam634-other")
        job = job_for(other)
        with self.assertRaises(CoachInvalid):
            proposals(self.content).create(
                CreateProposal(
                    AccountId(self.owner.pk), JobId(job.pk), proposal_decoder()(self.content), None
                )
            )
        row = draft(self.owner, self.content)
        with self.assertRaises(PlanProposal.DoesNotExist):
            accept_proposal(other, row.pk)
        with self.assertRaises(PlanProposal.DoesNotExist):
            edit_and_accept_proposal(other, row.pk, self.content)
        self.assertFalse(TrainingPlan.objects.exists())

    def test_exercise_must_have_been_in_authorized_catalog(self) -> None:
        job = job_for(self.owner)
        classification = Classification.objects.create(nombre="Fixture634")
        exercise = Exercise.objects.create(nombre="No enviado", classification=classification)
        content = copy.deepcopy(self.content)
        content["sessions"] = [
            {
                "title": "Fuerza",
                "date": "2027-01-04",
                "cycle_key": "micro",
                "blocks": [
                    {
                        "sport": "strength",
                        "title": "Serie",
                        "sets": [{"exercise": exercise.pk, "target_reps": 5}],
                    }
                ],
            }
        ]
        with self.assertRaises(CoachInvalid):
            proposals(content).create(
                CreateProposal(
                    AccountId(self.owner.pk), JobId(job.pk), proposal_decoder()(content), None
                )
            )
        self.assertFalse(PlanProposal.objects.exists())

    def test_distinct_goals_limited_equipment_and_no_history_need_no_model(self) -> None:
        for sport in ("running", "cycling", "swimming", "hiking"):
            with self.subTest(sport=sport):
                goal = Goal.objects.create(owner=self.owner, title="Meta " + sport, sport=sport)
                content = source(goal)
                content["sessions"] = [
                    {
                        "title": sport,
                        "date": "2027-01-04",
                        "cycle_key": "micro",
                        "blocks": [
                            {
                                "sport": sport,
                                "title": "Práctica",
                                "target": {"duration_seconds": 1200},
                            }
                        ],
                    }
                ]
                row = draft(self.owner, content)
                result = accept_proposal(self.owner, row.pk)
                self.assertEqual(TrainingPlan.objects.get(pk=result.pk).goal_id, goal.pk)
        self.assertFalse(Session.objects.exists())

    def test_invalid_units_references_hierarchy_and_actual_results_never_make_calendar(
        self,
    ) -> None:
        invalids = [
            [{"sport": "running", "title": "Mal", "target": {"distance_km": 3}}],
            [{"sport": "running", "title": "Mal", "actual": {"distance_m": 100}}],
        ]
        for blocks in invalids:
            content = copy.deepcopy(self.content)
            content["sessions"] = [
                {"title": "Mal", "date": "2027-01-04", "cycle_key": "micro", "blocks": blocks}
            ]
            with self.assertRaises((ValidationError, InvalidPlanning)):
                draft(self.owner, content)
        content = copy.deepcopy(self.content)
        content["cycles"] = []
        with self.assertRaises(ValidationError):
            draft(self.owner, content)
        self.assertFalse(PlanProposal.objects.exists())
        self.assertFalse(PlannedSession.objects.exists())

    def test_final_persistence_failure_rolls_back_edited_source_and_every_calendar_row(
        self,
    ) -> None:
        row = draft(self.owner, self.content)
        content = copy.deepcopy(self.content)
        content["title"] = "No debe persistir"
        original = DjangoProposalRepository.save

        def fail_final(
            repository: DjangoProposalRepository, proposal: Proposal, *, edited: bool = False
        ) -> None:
            if not edited:
                raise RuntimeError("MAM634 injected final persistence failure")
            original(repository, proposal, edited=edited)

        with patch.object(DjangoProposalRepository, "save", fail_final):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                edit_and_accept_proposal(self.owner, row.pk, content)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")
        self.assertIsNone(row.accepted_plan_id)
        self.assertEqual(row.content, self.content)
        self.assertFalse(TrainingPlan.objects.exists())
        self.assertFalse(PlannedSession.objects.exists())
        self.assertFalse(Block.objects.exists())
        self.assertIsNotNone(accept_proposal(self.owner, row.pk))

    def test_versions_and_restore_leave_historical_rows_unchanged(self) -> None:
        first = draft(self.owner, self.content)
        accepted = accept_proposal(self.owner, first.pk)
        base = TrainingPlan.objects.get(pk=accepted.pk)
        scheduled = PlannedSession.objects.get(plan=base)
        execution = Session.objects.create(
            owner=self.owner,
            planned=scheduled,
            title="Histórico",
            date=scheduled.date,
            status="completed",
            duration_seconds=1400,
        )
        Block.objects.create(
            session=execution,
            order=1,
            sport="running",
            title="Real",
            actual={"duration_seconds": 1400},
        )
        before_plan = list(TrainingPlan.objects.filter(pk=base.pk).values())
        before_session = list(Session.objects.filter(pk=execution.pk).values())
        before_blocks = list(Block.objects.filter(session=execution).values())
        content = copy.deepcopy(self.content)
        content["title"] = "Segunda versión"
        row = draft(self.owner, content, base)
        successor = accept_proposal(self.owner, row.pk)
        self.assertEqual(TrainingPlan.objects.get(pk=successor.pk).version, 2)
        restored = planning().restore(
            RestorePlan(
                AccountId(self.owner.pk),
                PlanId(successor.pk),
                PlanId(base.pk),
                "Restauración explícita del atleta",
            )
        )
        self.assertEqual(restored.version, 3)
        self.assertEqual(list(TrainingPlan.objects.filter(pk=base.pk).values()), before_plan)
        self.assertEqual(list(Session.objects.filter(pk=execution.pk).values()), before_session)
        self.assertEqual(list(Block.objects.filter(session=execution).values()), before_blocks)

    def test_changed_base_version_rejects_and_rolls_back_edit(self) -> None:
        accepted = accept_proposal(self.owner, draft(self.owner, self.content).pk)
        base = TrainingPlan.objects.get(pk=accepted.pk)
        row = draft(self.owner, self.content, base)
        planning().revise(RevisePlan(AccountId(self.owner.pk), PlanId(base.pk), "Cambio oficial"))
        content = copy.deepcopy(self.content)
        content["title"] = "No persistir"
        with self.assertRaises(ValidationError):
            edit_and_accept_proposal(self.owner, row.pk, content)
        row.refresh_from_db()
        self.assertEqual(row.content, self.content)
        self.assertEqual(TrainingPlan.objects.count(), 2)


class ProposalReview634Tests(TestCase):
    def setUp(self) -> None:
        self.owner = account("mam634-web")
        goal = Goal.objects.create(owner=self.owner, title="Constancia", sport="running")
        self.content = source(goal)
        self.row = draft(self.owner, self.content)
        self.url = reverse("proposal-review", args=[self.row.pk])
        self.client.force_login(self.owner)

    def fields(self) -> dict[str, object]:
        form = ProposalReviewForm(content=self.content, owner=self.owner)
        return {key: value if value is not None else "" for key, value in form.initial.items()}

    def test_comparison_before_apply_and_exact_posted_candidate(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, "Qué cambia")
        self.assertContains(response, "Motivo y supuestos")
        self.assertContains(response, "1800 s")
        self.assertNotContains(response, "Aceptar esta comparación")
        fields = self.fields()
        fields.update(decision="preview", value_0="Nombre editado", constraints_reviewed="on")
        preview = self.client.post(self.url, fields)
        self.assertContains(preview, "Nombre editado")
        self.assertContains(preview, "Aceptar esta comparación")
        self.assertFalse(TrainingPlan.objects.exists())
        fields.update(decision="accept", review_token=preview.context["review_token"])
        accepted = self.client.post(self.url, fields)
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(TrainingPlan.objects.get().title, "Nombre editado")
        retried = self.client.post(self.url, fields)
        self.assertEqual(retried.status_code, 302)
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_changed_fields_after_comparison_require_another_comparison(self) -> None:
        fields = self.fields()
        fields["decision"] = "preview"
        preview = self.client.post(self.url, fields)
        fields.update(
            decision="accept",
            review_token=preview.context["review_token"],
            value_0="Cambio no comparado",
            constraints_reviewed="on",
        )
        result = self.client.post(self.url, fields)
        self.assertContains(result, "Cambiaste campos", status_code=409)
        self.assertFalse(TrainingPlan.objects.exists())

    def test_reject_stale_source_is_explicit_conflict(self) -> None:
        page = self.client.get(self.url)
        content = copy.deepcopy(self.content)
        content["title"] = "Otra fuente"
        PlanProposal.objects.filter(pk=self.row.pk).update(content=content)
        result = self.client.post(
            self.url, {"decision": "reject", "review_token": page.context["review_token"]}
        )
        self.assertContains(result, "cambió desde tu revisión", status_code=409)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "pending")

    def test_invalid_draft_is_hidden_but_can_be_discarded_without_form_fields(self) -> None:
        PlanProposal.objects.filter(pk=self.row.pk).update(content={"bad": True})
        page = self.client.get(self.url)
        self.assertContains(page, "No se aplicó ningún cambio", status_code=400)
        self.assertNotContains(page, "Nombre del plan", status_code=400)
        rejected = self.client.post(
            self.url, {"decision": "reject", "review_token": page.context["review_token"]}
        )
        self.assertEqual(rejected.status_code, 302)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "rejected")


class ProposalConcurrency634Tests(TransactionTestCase):
    def setUp(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("Requires real PostgreSQL row locks")
        self.owner = account("mam634-race")
        goal = Goal.objects.create(owner=self.owner, title="Constancia", sport="running")
        self.content = source(goal)

    def race(
        self, actions: tuple[Callable[[], int | None], Callable[[], int | None]]
    ) -> list[int | str | None]:
        barrier = Barrier(2)

        def run(action: Callable[[], int | None]) -> int | str | None:
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                barrier.wait(timeout=10)
                try:
                    return action()
                except ValidationError:
                    return "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, action) for action in actions]
            return [future.result(timeout=20) for future in futures]

    def test_same_proposal_two_acceptances_return_one_successor_and_same_result(self) -> None:
        base_result = accept_proposal(self.owner, draft(self.owner, self.content).pk)
        base = TrainingPlan.objects.get(pk=base_result.pk)
        row = draft(self.owner, self.content, base)
        results = self.race(
            (
                lambda: accept_proposal(self.owner, row.pk).pk,
                lambda: accept_proposal(self.owner, row.pk).pk,
            )
        )
        self.assertEqual(results[0], results[1])
        self.assertIsInstance(results[0], int)
        self.assertEqual(TrainingPlan.objects.filter(previous=base).count(), 1)
        self.assertEqual(TrainingPlan.objects.count(), 2)

    def test_two_edited_acceptances_do_not_overwrite_the_winning_content(self) -> None:
        row = draft(self.owner, self.content)
        left, right = copy.deepcopy(self.content), copy.deepcopy(self.content)
        left["title"], right["title"] = "Izquierda", "Derecha"
        key = review_key(row)
        results = self.race(
            (
                lambda: edit_and_accept_proposal(self.owner, row.pk, left, key).pk,
                lambda: edit_and_accept_proposal(self.owner, row.pk, right, key).pk,
            )
        )
        self.assertEqual(results.count("conflict"), 1)
        row.refresh_from_db()
        self.assertEqual(row.content["title"], TrainingPlan.objects.get().title)

    def test_accept_and_reviewed_reject_have_one_consistent_decision(self) -> None:
        row = draft(self.owner, self.content)
        key = review_key(row)
        results = self.race(
            (
                lambda: accept_proposal(self.owner, row.pk).pk,
                lambda: reject_proposal(self.owner, row.pk, key),
            )
        )
        self.assertEqual(results.count("conflict"), 1)
        row.refresh_from_db()
        self.assertEqual(TrainingPlan.objects.count(), int(row.status == "accepted"))

    def assert_guard_retains_lock_through_creation(
        self, row: PlanProposal, writer: Callable[[], None], expected_sql: str
    ) -> None:
        pids: Queue[int] = Queue()
        done = Event()
        original = DjangoCoachPlanning.create
        future: Future[None] | None = None

        def write() -> None:
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '12s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(int(cursor.fetchone()[0]))
                writer()
                done.set()
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=1) as pool:

            def create(
                gateway: DjangoCoachPlanning,
                owner: AccountId,
                definition: PlanDefinition,
                previous: PlanId | None,
            ) -> PlanId:
                nonlocal future
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    holder = int(cursor.fetchone()[0])
                future = pool.submit(write)
                writer_pid = pids.get(timeout=3)
                deadline = monotonic() + 4
                statement = ""
                while monotonic() < deadline and not done.is_set():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute(
                            "SELECT wait_event_type, query, pg_blocking_pids(pid) "
                            "FROM pg_stat_activity WHERE pid = %s",
                            [writer_pid],
                        )
                        state = cursor.fetchone()
                    if state is not None and state[0] == "Lock" and holder in state[2]:
                        statement = str(state[1])
                        break
                    done.wait(0.01)
                self.assertIn(expected_sql, statement)
                self.assertFalse(done.is_set())
                return original(gateway, owner, definition, previous)

            # The patched boundary only coordinates the real competing connection.
            # Snapshot/guard/plan persistence/outer commit are the production path.
            with patch.object(DjangoCoachPlanning, "create", create):
                accepted = accept_proposal(self.owner, row.pk)
            assert future is not None
            future.result(timeout=10)
        self.assertTrue(done.is_set())
        self.assertEqual(accept_proposal(self.owner, row.pk).pk, accepted.pk)

    def test_guard_keeps_preferences_locked_after_check_until_plan_commit(self) -> None:
        from basis.bootstrap.athletes import athletes
        from basis.modules.athletes.adapters.django import DjangoAthleteRecords
        from basis.modules.athletes.public import EditPreferences

        row = draft(self.owner, self.content)
        data = replace(
            DjangoAthleteRecords().preferences(AccountId(self.owner.pk)), availability=(2,)
        )

        def writer() -> None:
            athletes().edit_preferences(EditPreferences(AccountId(self.owner.pk), data))

        self.assert_guard_retains_lock_through_creation(
            row, writer, 'UPDATE "basis_athletes_athletesettings"'
        )
        self.assertEqual(AthleteSettings.objects.get(owner=self.owner).availability, [2])

    def test_guard_locks_referenced_catalog_rows_from_all_sets_until_commit(self) -> None:
        classification = Classification.objects.create(nombre="Guard634")
        first = Exercise.objects.create(nombre="Primero", classification=classification)
        last = Exercise.objects.create(nombre="Último", classification=classification)
        content = copy.deepcopy(self.content)
        content["sessions"] = [
            {
                "title": "Fuerza",
                "date": "2027-01-04",
                "cycle_key": "micro",
                "blocks": [
                    {
                        "sport": "strength",
                        "title": "Series",
                        "sets": [
                            {"exercise": last.pk, "target_reps": 5},
                            {"exercise": first.pk, "target_reps": 3},
                            {"exercise": last.pk, "target_reps": 2},
                        ],
                    }
                ],
            }
        ]
        row = draft(self.owner, content)

        def writer() -> None:
            Exercise.objects.filter(pk=last.pk).update(nombre="Después del commit")

        self.assert_guard_retains_lock_through_creation(
            row, writer, 'UPDATE "basis_catalog_exercise"'
        )
        self.assertEqual(Exercise.objects.get(pk=last.pk).nombre, "Después del commit")

    def test_guard_keeps_goal_locked_until_commit(self) -> None:
        base_result = accept_proposal(self.owner, draft(self.owner, self.content).pk)
        base = TrainingPlan.objects.get(pk=base_result.pk)
        row = draft(self.owner, self.content, base)

        def writer() -> None:
            Goal.objects.filter(pk=base.goal_id).update(title="Meta después de aceptar")

        self.assert_guard_retains_lock_through_creation(row, writer, 'UPDATE "basis_training_goal"')
        self.assertEqual(TrainingPlan.objects.filter(previous=base).count(), 1)
