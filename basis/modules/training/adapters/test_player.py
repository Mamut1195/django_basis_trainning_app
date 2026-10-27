"""MAM-628: real web/application persistence, isolation and revision checks."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.models import Block, Session, StrengthSet
from basis.modules.training.adapters.web.player import QuickSetForm
from tests.regression.contracts import build_plan
from tests.regression.factories import account, exercise, proposal

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


class PlayerTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("player628")
        self.other = account("foreign628")
        self.exercise = exercise()
        content = proposal(self.owner)
        content["sessions"][0]["blocks"] = [
            {
                "sport": "strength",
                "title": "Fuerza privada",
                "sets": [
                    {"exercise": self.exercise.pk, "target_reps": 5, "target_kg": "80"},
                    {"exercise": self.exercise.pk, "target_reps": 8, "target_kg": "60"},
                ],
            }
        ]
        self.plan = build_plan(self.owner, content)
        self.session = start_session(self.owner, self.plan.sessions.get())
        self.row = self.session.blocks.get().sets.all()[0]
        self.url = reverse("player-set", args=[self.row.pk])
        self.client.force_login(self.owner)

    def send(self, **changes: object) -> _MonkeyPatchedWSGIResponse:
        return self.client.post(
            self.url,
            {
                "revision": self.session.revision,
                "actual_reps": "4",
                "actual_kg": "75.25",
                "actual_rpe": "8.5",
                "actual_rir": "",
                **changes,
            },
            HTTP_ACCEPT="application/json",
        )

    def test_real_results_do_not_mutate_prescription_or_invent_rir(self) -> None:
        response = self.send(target_kg="999", target_reps="999", owner=self.other.pk)
        self.assertEqual(response.status_code, 200, response.content)
        self.row.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(
            (self.row.actual_reps, self.row.actual_kg, self.row.actual_rpe),
            (4, Decimal("75.25"), Decimal("8.5")),
        )
        self.assertIsNone(self.row.actual_rir)
        self.assertEqual((self.row.target_reps, self.row.target_kg), (5, Decimal("80")))
        self.assertEqual(self.session.revision, 2)
        self.assertIsNone(self.plan.sessions.get().blocks.get().sets.all()[0].actual_reps)

    def test_zero_and_missing_are_distinct_and_undo_is_compensating_write(self) -> None:
        self.assertEqual(self.send(actual_reps="0", actual_kg="0", actual_rpe="0").status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual((self.row.actual_reps, self.row.actual_kg, self.row.actual_rpe), (0, 0, 0))
        self.session.refresh_from_db()
        self.assertEqual(self.send(actual_reps="", actual_kg="", actual_rpe="").status_code, 200)
        self.row.refresh_from_db()
        self.assertIsNone(self.row.actual_kg)
        self.assertIsNone(self.row.actual_reps)

    def test_invalid_fields_do_not_commit_or_consume_revision(self) -> None:
        for field, value in (
            ("actual_reps", "-1"),
            ("actual_reps", "2.5"),
            ("actual_kg", "NaN"),
            ("actual_kg", "100000"),
            ("actual_rpe", "11"),
            ("actual_rir", "21"),
        ):
            with self.subTest(field=field):
                self.assertEqual(self.send(**{field: value}).status_code, 400)
        self.session.refresh_from_db()
        self.row.refresh_from_db()
        self.assertEqual(self.session.revision, 1)
        self.assertIsNone(self.row.actual_kg)

    def test_stale_revision_does_not_overwrite_results(self) -> None:
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send(actual_kg="1").status_code, 409)
        self.row.refresh_from_db()
        self.assertEqual(self.row.actual_kg, Decimal("75.25"))

    def test_foreign_account_cannot_read_save_or_complete(self) -> None:
        self.client.force_login(self.other)
        self.assertEqual(self.send().status_code, 404)
        self.assertEqual(
            self.client.get(reverse("session-detail", args=[self.session.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.post(
                reverse("player-complete", args=[self.session.pk]), {"revision": 1, "confirm": "on"}
            ).status_code,
            404,
        )

    def test_post_and_csrf_required(self) -> None:
        self.assertEqual(self.client.get(self.url).status_code, 405)
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.owner)
        self.assertEqual(guarded.post(self.url, {"revision": 1}).status_code, 403)

    def test_read_only_billing_and_anonymous_cannot_write(self) -> None:
        self.owner.billing.status = "inactive"
        self.owner.billing.save()
        self.assertEqual(self.send().status_code, 403)
        self.client.logout()
        self.assertEqual(self.send().status_code, 302)

    def test_partial_close_preserves_absence_and_is_immutable(self) -> None:
        self.assertEqual(self.send().status_code, 200)
        self.session.refresh_from_db()
        close = reverse("player-complete", args=[self.session.pk])
        self.assertEqual(
            self.client.post(close, {"revision": self.session.revision}).status_code, 400
        )
        self.assertEqual(self.client.post(close, {"revision": 1, "confirm": "on"}).status_code, 409)
        self.assertEqual(
            self.client.post(
                close, {"revision": self.session.revision, "confirm": "on"}
            ).status_code,
            302,
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "completed")
        self.assertIsNone(self.session.blocks.get().sets.all()[1].actual_reps)
        self.assertIn(self.send(revision=self.session.revision).status_code, (400, 404, 409))

    def test_today_prioritizes_owner_active_session_and_checkin(self) -> None:
        Session.objects.create(owner=self.other, title="FOREIGN SECRET")
        response = self.client.get("/")
        self.assertContains(response, "Continuar sesión")
        self.assertContains(response, "Antes de empezar")
        self.assertContains(response, "Tu dirección")
        self.assertNotContains(response, "FOREIGN SECRET")

    def test_previous_reference_is_private_completed_and_never_prefilled(self) -> None:
        previous = Session.objects.create(owner=self.owner, title="Anterior", status="completed")
        previous_block = Block.objects.create(session=previous, sport="strength", title="Anterior")
        StrengthSet.objects.create(
            block=previous_block, exercise=self.exercise, actual_reps=6, actual_kg=Decimal("71.25")
        )
        foreign = Session.objects.create(
            owner=self.other, title="FOREIGN SECRET", status="completed"
        )
        foreign_block = Block.objects.create(session=foreign, sport="strength", title="Otra")
        StrengthSet.objects.create(
            block=foreign_block, exercise=self.exercise, actual_reps=99, actual_kg=Decimal("999.99")
        )
        response = self.client.get(reverse("session-detail", args=[self.session.pk]))
        self.assertContains(response, "71,25")
        self.assertNotContains(response, "999,99")
        self.assertContains(response, f'id="kg-{self.row.pk}"')
        self.assertIsNone(StrengthSet.objects.get(pk=self.row.pk).actual_kg)

    def test_session_detail_query_count_is_constant_as_series_grow(self) -> None:
        previous = Session.objects.create(owner=self.owner, title="Anterior", status="completed")
        block = Block.objects.create(session=previous, sport="strength", title="Anterior")
        reference = StrengthSet.objects.create(
            block=block, exercise=self.exercise, actual_reps=0, actual_kg=Decimal("0")
        )
        url = reverse("session-detail", args=[self.session.pk])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The entire rendered request stays bounded, including dates in reference labels.
        self.assertEqual(sum("ROW_NUMBER()" in query["sql"] for query in queries), 1)
        current_block = self.session.blocks.get()
        for order in range(3, 23):
            StrengthSet.objects.create(
                block=current_block, exercise=self.exercise, order=order, target_reps=5
            )
        with self.assertNumQueries(len(queries)):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        quick_sets = response.context["quick_sets"]
        self.assertEqual(len(quick_sets), 22)
        self.assertTrue(all(prior.pk == reference.pk for _, prior in quick_sets))

    def test_previous_reference_preserves_dimensions_and_latest_order(self) -> None:
        alternate = exercise()
        StrengthSet.objects.filter(pk=self.row.pk).update(
            actual_exercise=alternate, actual_load_type="assisted", actual_side="left"
        )
        previous = Session.objects.create(owner=self.owner, title="Anterior", status="completed")
        block = Block.objects.create(session=previous, sport="strength", title="Anterior")
        reference = StrengthSet.objects.create(
            block=block, exercise=alternate, load_type="assisted", side="left", actual_reps=3
        )
        # Same session/date: the last PK wins. Actual dimensions override prescriptions.
        reference = StrengthSet.objects.create(
            block=block,
            exercise=self.exercise,
            actual_exercise=alternate,
            actual_load_type="assisted",
            actual_side="left",
            actual_reps=4,
            adaptation_reason="Adaptación ficticia de prueba",
        )
        for load_type, side in (("external", "left"), ("assisted", "right")):
            StrengthSet.objects.create(
                block=block, exercise=alternate, load_type=load_type, side=side, actual_reps=99
            )
        StrengthSet.objects.create(block=block, exercise=alternate, actual_reps=None)
        # A later creation timestamp beats PK, but a later training date beats creation.
        older = Session.objects.create(
            owner=self.owner,
            title="Más antigua",
            status="completed",
            date=self.session.date - timedelta(days=1),
        )
        older_block = Block.objects.create(session=older, sport="strength", title="Antigua")
        StrengthSet.objects.create(
            block=older_block,
            exercise=alternate,
            load_type="assisted",
            side="left",
            actual_reps=88,
        )
        for status, day in (("in_progress", 0), ("completed", 1)):
            excluded = Session.objects.create(
                owner=self.owner,
                title="No comparable",
                status=status,
                date=self.session.date + timedelta(days=day),
            )
            excluded_block = Block.objects.create(session=excluded, sport="strength", title="Otra")
            StrengthSet.objects.create(
                block=excluded_block,
                exercise=alternate,
                load_type="assisted",
                side="left",
                actual_reps=77,
            )
        url = reverse("session-detail", args=[self.session.pk])
        response = self.client.get(url)
        matches = {row.pk: prior for row, prior in response.context["quick_sets"]}
        self.assertEqual(matches[self.row.pk].pk, reference.pk)
        self.assertIsNone(matches[self.session.blocks.get().sets.all()[1].pk])
        # Ordering within the same date uses session creation before row PK.
        recent = Session.objects.create(owner=self.owner, title="Reciente", status="completed")
        recent_block = Block.objects.create(session=recent, sport="strength", title="Reciente")
        recent_reference = StrengthSet.objects.create(
            block=recent_block, exercise=alternate, load_type="assisted", side="left", actual_reps=5
        )
        Session.objects.filter(pk=recent.pk).update(
            created_at=timezone.now() + timedelta(seconds=1)
        )
        response = self.client.get(url)
        matches = {row.pk: prior for row, prior in response.context["quick_sets"]}
        self.assertEqual(matches[self.row.pk].pk, recent_reference.pk)

    def test_model_form_reuses_domain_validation(self) -> None:
        form = QuickSetForm(
            {"actual_reps": "4", "actual_kg": "75", "actual_rpe": "8.5"}, instance=self.row
        )
        self.assertTrue(form.is_valid(), form.errors)
