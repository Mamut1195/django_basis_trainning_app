"""Private measured and estimated strength mark history."""

from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from basis.bootstrap.marks import estimated_marks
from basis.modules.athletes.adapters.models import UserExerciseRM
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.training.adapters.models import Block, Session, StrengthSet
from basis.shared.identifiers import AccountId, ExerciseId
from tests.regression.factories import account


class StrengthMarksTests(TestCase):
    def setUp(self) -> None:
        self.user = account("marks-owner")
        self.other = account("marks-other")
        classification = Classification.objects.create(nombre="Fuerza marcas")
        self.exercise = Exercise.objects.create(
            nombre="Sentadilla marcas", classification=classification
        )
        self.archived = Exercise.objects.create(
            nombre="Variante archivada", classification=classification, archivado=True
        )
        self.foreign_exercise = Exercise.objects.create(
            nombre="Ejercicio ajeno", classification=classification
        )
        self.today = date(2026, 1, 5)
        self.session = Session.objects.create(
            owner=self.user, title="Sesión privada", date=self.today, status="completed"
        )
        self.block = Block.objects.bulk_create(
            [Block(session=self.session, title="Bloque A", sport="strength")]
        )[0]
        self.foreign_session = Session.objects.create(
            owner=self.other, title="Sesión ajena privada", date=self.today, status="completed"
        )
        self.foreign_block = Block.objects.bulk_create(
            [Block(session=self.foreign_session, title="Ajeno", sport="strength")]
        )[0]
        self.client.force_login(self.user)
        self.url = reverse("strength-marks")

    def series(self, **values: object) -> StrengthSet:
        data = {
            "block": self.block,
            "exercise": self.exercise,
            "actual_kg": Decimal("80"),
            "actual_reps": 5,
            "actual_rpe": Decimal("10"),
            **values,
        }
        return StrengthSet.objects.bulk_create([StrengthSet(**data)])[0]

    def test_sql_eligibility_matches_domain_and_effective_fields(self) -> None:
        rows = [
            self.series(),
            self.series(kind="warmup", actual_kind="work"),
            self.series(kind="work", actual_kind="warmup"),
            self.series(load_type="bodyweight", actual_load_type="external"),
            self.series(load_type="external", actual_load_type="bodyweight"),
            self.series(load_type="assisted"),
            self.series(actual_rpe=None),
            self.series(actual_rpe=0),
            self.series(actual_kg=0),
            self.series(actual_reps=11),
            self.series(actual_reps=1),
            self.series(actual_reps=10),
            self.series(actual_reps=0),
            self.series(actual_reps=None),
            self.series(actual_kg=None),
            self.series(actual_kind="", actual_load_type=""),
            self.series(actual_exercise=self.archived),
        ]
        partial = Session.objects.create(
            owner=self.user, title="Parcial", date=self.today, status="in_progress"
        )
        partial_block = Block.objects.bulk_create(
            [Block(session=partial, title="Partial", sport="strength")]
        )[0]
        self.series(block=partial_block)
        self.series(block=self.foreign_block, exercise=self.foreign_exercise)
        result = estimated_marks().read(AccountId(self.user.pk), None, None, None, 1)
        expected = {row.pk for row in rows if row.estimated_1rm is not None}
        self.assertEqual({int(mark.set_id) for mark in result.rows}, expected)
        self.assertEqual(result.total, len(expected))
        archived = estimated_marks().read(
            AccountId(self.user.pk), ExerciseId(self.archived.pk), None, None, 1
        )
        self.assertEqual(len(archived.rows), 1)
        self.assertEqual(archived.rows[0].exercise_name, self.archived.nombre)
        self.assertEqual(archived.rows[0].kg, Decimal("93.33"))
        response = self.client.get(self.url)
        self.assertContains(response, self.archived.nombre + " (archivado)")
        self.assertContains(response, "Bloque A / serie")
        self.assertNotContains(response, "Sesión ajena privada")

    def test_private_source_links_filters_and_read_only(self) -> None:
        own = UserExerciseRM.objects.create(
            user=self.user.athlete,
            exercise=self.exercise,
            peso_maximo_rm=Decimal("90"),
            fecha_registro=self.today,
        )
        foreign = UserExerciseRM.objects.create(
            user=self.other.athlete,
            exercise=self.foreign_exercise,
            peso_maximo_rm=Decimal("110"),
            fecha_registro=self.today,
        )
        self.assertContains(self.client.get(self.url), reverse("measured-rm-detail", args=[own.pk]))
        self.series(actual_exercise=self.archived)
        self.assertEqual(
            self.client.get(reverse("measured-rm-detail", args=[own.pk])).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("measured-rm-detail", args=[foreign.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.post(reverse("measured-rm-detail", args=[own.pk])).status_code, 405
        )
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(
            self.client.get(self.url, {"exercise": self.foreign_exercise.pk})
            .context["measured"]
            .total,
            0,
        )
        self.assertEqual(
            self.client.get(self.url, {"exercise": self.foreign_exercise.pk})
            .context["estimated"]
            .total,
            0,
        )
        filtered = self.client.get(
            self.url,
            {"exercise": str(self.archived.pk), "start": "2026-01-05", "end": "2026-01-05"},
        )
        self.assertEqual(filtered.context["estimated"].total, 1)
        self.assertEqual(filtered.context["measured"].total, 0)
        self.assertContains(filtered, reverse("session-detail", args=[self.session.pk]))
        self.assertEqual(
            self.client.get(self.url, {"start": "2026-01-06", "end": "2026-01-05"}).status_code, 400
        )
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_pagination_query_bound_and_no_mutation_or_export_truncation(self) -> None:
        UserExerciseRM.objects.bulk_create(
            [
                UserExerciseRM(
                    user=self.user.athlete,
                    exercise=self.exercise,
                    peso_maximo_rm=Decimal("50"),
                    fecha_registro=self.today - timedelta(days=i),
                )
                for i in range(25)
            ]
        )
        StrengthSet.objects.bulk_create(
            [
                StrengthSet(
                    block=self.block,
                    exercise=self.exercise,
                    order=i + 1,
                    actual_kg=80,
                    actual_reps=5,
                    actual_rpe=10,
                )
                for i in range(25)
            ]
        )
        before = (UserExerciseRM.objects.count(), StrengthSet.objects.count())
        with CaptureQueriesContext(connection) as queries:
            first = self.client.get(self.url, {"exercise": self.exercise.pk})
        self.assertEqual(len(first.context["measured"].rows), 20)
        self.assertEqual(len(first.context["estimated"].rows), 20)
        self.assertLessEqual(len(queries), 10)
        second = self.client.get(
            self.url,
            {"exercise": str(self.exercise.pk), "measured_page": "2", "estimated_page": "2"},
        )
        self.assertEqual(
            (len(second.context["measured"].rows), len(second.context["estimated"].rows)), (5, 5)
        )
        self.assertTrue(
            set(mark.set_id for mark in first.context["estimated"].rows).isdisjoint(
                mark.set_id for mark in second.context["estimated"].rows
            )
        )
        self.assertEqual(
            [mark.set_id for mark in first.context["estimated"].rows],
            sorted((mark.set_id for mark in first.context["estimated"].rows), reverse=True),
        )
        for bad in ("invalid", "-2", "999999"):
            self.assertEqual(
                self.client.get(
                    self.url, {"measured_page": bad, "estimated_page": bad}
                ).status_code,
                200,
            )
        self.assertEqual((UserExerciseRM.objects.count(), StrengthSet.objects.count()), before)
        export = self.client.get(reverse("export")).json()
        self.assertEqual(len(export["userexerciserm"]), 25)

    def test_inclusive_dates_legacy_zero_and_progress_link(self) -> None:
        for delta in (-1, 0, 1):
            day = self.today + timedelta(days=delta)
            UserExerciseRM.objects.create(
                user=self.user.athlete,
                exercise=self.exercise,
                peso_maximo_rm=Decimal("50"),
                fecha_registro=day,
            )
            session = Session.objects.create(
                owner=self.user, title="date fixture", date=day, status="completed"
            )
            block = Block.objects.bulk_create(
                [Block(session=session, title="date block", sport="strength")]
            )[0]
            self.series(block=block)
        legacy = UserExerciseRM.objects.bulk_create(
            [
                UserExerciseRM(
                    user=self.user.athlete,
                    exercise=self.exercise,
                    peso_maximo_rm=Decimal(0),
                    fecha_registro=self.today,
                )
            ]
        )[0]
        response = self.client.get(self.url, {"start": "2026-01-05", "end": "2026-01-05"})
        self.assertEqual(response.context["measured"].total, 1)
        self.assertEqual(response.context["estimated"].total, 1)
        detail = self.client.get(reverse("measured-rm-detail", args=[legacy.pk]))
        self.assertContains(detail, "no es una marca válida")
        self.assertEqual(len(self.client.get(reverse("export")).json()["userexerciserm"]), 4)
        progress = self.client.get("/progress/", {"period": "week", "reference": "2026-01-05"})
        self.assertContains(
            progress, reverse("strength-marks") + "?start=2026-01-05&amp;end=2026-01-11"
        )
