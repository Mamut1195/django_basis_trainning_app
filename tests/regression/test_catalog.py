"""MAM-621: real catalog reads, lineage, permissions and prescribed substitutions."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from basis.modules.athletes.adapters.models import UserExerciseRM
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.training.adapters.actions import revise_plan, start_session
from basis.modules.training.adapters.models import StrengthSet

from .contracts import build_plan, required
from .factories import account, proposal, session


class CatalogTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("catalog-owner")
        self.other = account("catalog-other")
        self.staff = account("catalog-staff")
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        self.classification = Classification.objects.create(nombre="Fuerza")
        self.base = Exercise.objects.create(
            nombre="Sentadilla con barra",
            classification=self.classification,
            equipo="Barra y discos",
            patron_movimiento="Sentadilla",
            nivel_fatiga="Alto",
        )
        self.variant = Exercise.objects.create(
            nombre="Sentadilla goblet",
            classification=self.classification,
            equipo="Mancuerna",
            patron_movimiento="Sentadilla",
            nivel_fatiga="Medio",
            variante="Goblet",
            variante_de=self.base,
        )
        self.client = APIClient()
        self.client.force_login(self.owner)

    def test_filters_combine_and_do_not_infer_equipment_equivalence(self) -> None:
        params: dict[str, str | int] = {
            "q": "GOBLET",
            "classification": self.classification.pk,
            "equipo": "mancuerna",
            "patron_movimiento": "sentadilla",
            "nivel_fatiga": "Medio",
            "variante": "goblet",
            "variante_de": self.base.pk,
        }
        response = self.client.get("/api/v1/exercises/", params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["id"] for r in response.json()["results"]], [self.variant.pk])
        self.assertEqual(response.json()["results"][0]["variante_de"], self.base.pk)
        # "Barra" does not mean the exact declared requirement "Barra y discos".
        self.assertEqual(
            self.client.get("/api/v1/exercises/", {"equipo": "Barra"}).json()["count"], 0
        )
        self.assertEqual(
            self.client.get("/api/v1/exercises/", {**params, "nivel_fatiga": "Bajo"}).json()[
                "count"
            ],
            0,
        )

    def test_invalid_filter_values_are_400_without_query_broadening(self) -> None:
        for params in (
            {"classification": "not-an-id"},
            {"variante_de": -1},
            {"archivado": "perhaps"},
            {"nivel_fatiga": "Intenso"},
            {"q": "x" * 256},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/v1/exercises/", params).status_code, 400)

    def test_filtered_pagination_is_stable_even_with_equal_names(self) -> None:
        Exercise.objects.bulk_create(
            [
                Exercise(
                    nombre="Sentadilla duplicada",
                    classification=self.classification,
                    equipo="Mancuerna",
                )
                for _ in range(55)
            ]
        )
        first = self.client.get("/api/v1/exercises/", {"equipo": "Mancuerna"}).json()
        second = self.client.get("/api/v1/exercises/", {"equipo": "Mancuerna", "page": "2"}).json()
        self.assertEqual((first["count"], second["count"]), (56, 56))
        self.assertEqual((len(first["results"]), len(second["results"])), (50, 6))
        self.assertIsNotNone(first["next"])
        self.assertIsNone(second["next"])
        ids = [row["id"] for row in [*first["results"], *second["results"]]]
        self.assertEqual(len(set(ids)), 56)
        self.assertNotIn(self.base.pk, ids)

    def test_catalog_permissions_include_filters_and_archive_access(self) -> None:
        self.client.logout()
        self.assertEqual(self.client.get("/api/v1/exercises/", {"q": "goblet"}).status_code, 403)
        for user in (self.owner, self.other):
            self.client.force_login(user)
            self.assertEqual(self.client.get("/api/v1/exercises/").status_code, 200)
            self.assertEqual(
                self.client.get("/api/v1/exercises/", {"archivado": True}).status_code, 403
            )
            self.assertEqual(
                self.client.post("/api/v1/exercises/", {"nombre": "Injected"}).status_code, 403
            )
            detail = f"/api/v1/exercises/{self.variant.pk}/"
            self.assertEqual(self.client.patch(detail, {"archivado": True}).status_code, 403)
            self.assertEqual(self.client.delete(detail).status_code, 403)
        self.variant.refresh_from_db()
        self.assertFalse(self.variant.archivado)

    def test_staff_create_variant_archive_and_restore_with_explicit_archive_filter(self) -> None:
        self.client.force_login(self.staff)
        created = self.client.post(
            "/api/v1/exercises/",
            {
                "nombre": "Sentadilla frontal",
                "classification_id": self.classification.pk,
                "variante_de": self.base.pk,
                "equipo": "Barra y discos",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        row = Exercise.objects.get(pk=created.json()["id"])
        self.assertEqual(row.variante_de_id, self.base.pk)
        detail = f"/api/v1/exercises/{row.pk}/"
        self.assertEqual(self.client.patch(detail, {"archivado": True}).status_code, 200)
        self.assertEqual(self.client.get(detail).status_code, 404)
        archived = self.client.get("/api/v1/exercises/", {"archivado": True}).json()["results"]
        self.assertEqual([r["id"] for r in archived], [row.pk])
        self.assertEqual(
            self.client.patch(detail + "?archivado=true", {"archivado": False}).status_code, 200
        )
        self.assertEqual(self.client.get(detail).status_code, 200)

    def test_lineage_rejects_self_and_indirect_cycles_via_model_and_api(self) -> None:
        self.base.variante_de = self.base
        with self.assertRaises(ValidationError):
            self.base.save()
        self.base.refresh_from_db()
        grandchild = Exercise.objects.create(
            nombre="Goblet con pausa",
            classification=self.classification,
            variante_de=self.variant,
        )
        self.client.force_login(self.staff)
        response = self.client.patch(
            f"/api/v1/exercises/{self.base.pk}/", {"variante_de": grandchild.pk}
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("variante_de", response.json())
        self.base.refresh_from_db()
        self.assertIsNone(self.base.variante_de_id)
        invalid = self.client.post(
            "/api/v1/exercises/",
            {
                "nombre": "Invalid parent",
                "classification_id": self.classification.pk,
                "variante_de": 999999,
            },
        )
        self.assertEqual(invalid.status_code, 400)

    def test_variant_parent_deletion_is_protected_even_after_archive(self) -> None:
        self.base.archivado = True
        self.base.save(update_fields=["archivado"])
        with self.assertRaises(ProtectedError):
            self.base.delete()
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.delete(f"/api/v1/exercises/{self.base.pk}/?archivado=true").status_code,
            409,
        )
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.variante_de_id, self.base.pk)

    def test_lineage_validation_query_count_is_independent_of_depth(self) -> None:
        previous = self.base
        query_counts = []
        for depth in range(1, 33):
            row = Exercise.objects.create(
                nombre=f"Depth {depth}",
                classification=self.classification,
                variante_de=previous,
            )
            if depth in (1, 8, 32):
                with CaptureQueriesContext(connection) as queries:
                    row.full_clean()
                query_counts.append(len(queries))
            previous = row
        self.assertEqual(query_counts, [3, 3, 3])

    def test_list_queries_do_not_grow_with_classifications_or_variant_parents(self) -> None:
        def read_queries() -> tuple[int, int]:
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get("/api/v1/exercises/")
                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    all(row["classification"]["nombre"] for row in response.json()["results"])
                )
            catalog_queries = [q for q in queries if '"basis_catalog_' in q["sql"]]
            # COUNT + one joined page; FK parent serializes as its ID.
            self.assertEqual(len(catalog_queries), 2)
            return len(queries), response.json()["count"]

        small, _ = read_queries()
        for number in range(15):
            classification = Classification.objects.create(nombre=f"Clasificación {number}")
            Exercise.objects.create(
                nombre=f"Variante {number}",
                classification=classification,
                variante_de=self.base,
            )
        large, count = read_queries()
        self.assertEqual(count, 17)
        self.assertEqual(small, large)

    def test_versioned_substitution_preserves_original_and_archived_history(self) -> None:
        measured = UserExerciseRM.objects.create(
            user=self.owner.athlete,
            exercise=self.base,
            peso_maximo_rm=100,
            fecha_registro=timezone.localdate(),
        )
        content = proposal(self.owner)
        content["sessions"][0]["blocks"] = [
            {
                "sport": "strength",
                "title": "Fuerza",
                "sets": [
                    {
                        "exercise": self.base.pk,
                        "target_reps": 5,
                        "target_kg": "40.25",
                        "rm_reference": measured.pk,
                    }
                ],
            }
        ]
        content["sessions"].append(
            {
                **content["sessions"][0],
                "date": (timezone.localdate() + timedelta(days=1)).isoformat(),
            }
        )
        original = build_plan(self.owner, content)
        first = required(original.sessions.order_by("date").first())
        historical = start_session(self.owner, first)
        historical.status = "completed"
        historical.save(update_fields=["status"])
        revised = revise_plan(self.owner, original)
        self.assertEqual(revised.previous_id, original.pk)
        self.assertEqual(revised.lineage, original.lineage)
        self.assertEqual(revised.version, original.version + 1)
        new_row = StrengthSet.objects.get(block__planned__plan=revised)
        old_row = StrengthSet.objects.get(
            block__planned__plan=original,
            block__planned__date=required(new_row.block.planned).date,
        )
        payload = {
            "revision": 1,
            "exercise": self.variant.pk,
            "kind": "work",
            "load_type": "external",
            "side": "both",
            "target_reps": 5,
            "target_kg": "20.25",
        }
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f"/sets/{new_row.pk}/edit/", payload).status_code, 404)
        self.client.force_login(self.owner)
        invalid = self.client.post(
            f"/sets/{new_row.pk}/edit/", {**payload, "rm_reference": measured.pk}
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertTrue(invalid.context["form"].errors)
        new_row.refresh_from_db()
        self.assertEqual(
            (new_row.exercise_id, new_row.rm_reference_id), (self.base.pk, measured.pk)
        )
        response = self.client.post(f"/sets/{new_row.pk}/edit/", payload)
        self.assertEqual(response.status_code, 302, response.content)
        new_row.refresh_from_db()
        old_row.refresh_from_db()
        self.assertEqual((old_row.exercise_id, old_row.target_kg), (self.base.pk, Decimal("40.25")))
        self.assertEqual(
            (new_row.exercise_id, new_row.target_kg), (self.variant.pk, Decimal("20.25"))
        )
        self.assertEqual(old_row.rm_reference_id, measured.pk)
        self.assertIsNone(new_row.rm_reference_id)
        execution = start_session(self.owner, required(revised.sessions.first()))
        self.assertEqual(
            StrengthSet.objects.get(block__session=execution).exercise_id, self.variant.pk
        )
        self.base.archivado = True
        self.base.save(update_fields=["archivado"])
        self.assertContains(self.client.get(f"/sessions/{historical.pk}/"), self.base.nombre)
        self.assertContains(self.client.get(f"/sessions/{execution.pk}/"), self.variant.nombre)
        self.assertEqual(self.client.get(f"/api/v1/exercises/{self.base.pk}/").status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/sessions/{historical.pk}/").status_code, 404)

    def test_equipment_variants_keep_contract_load_types_and_decimal_kg(self) -> None:
        item = session(self.owner, "strength")
        block = required(item.blocks.first())
        for number, load_type in enumerate(("external", "bodyweight", "assisted"), start=1):
            response = self.client.post(
                f"/blocks/{block.pk}/sets/new/",
                {
                    "revision": number,
                    "exercise": self.variant.pk,
                    "kind": "work",
                    "load_type": load_type,
                    "side": ("both", "left", "right")[number - 1],
                    "target_reps": 5,
                    "actual_reps": 5,
                    "target_kg": "20.25",
                    "actual_kg": "0.00" if load_type == "bodyweight" else "12.25",
                    "bodyweight_kg": "70.50",
                },
            )
            self.assertEqual(response.status_code, 302, response.content)
        rows = list(StrengthSet.objects.filter(block=block))
        self.assertEqual([r.load_type for r in rows], ["external", "bodyweight", "assisted"])
        self.assertEqual([r.side for r in rows], ["both", "left", "right"])
        self.assertEqual([r.target_kg for r in rows], [Decimal("20.25")] * 3)
        self.assertEqual(rows[1].actual_kg, Decimal("0.00"))
        self.assertEqual(rows[2].actual_kg, Decimal("12.25"))
        self.assertEqual(rows[0].external_volume_kg, Decimal("61.25"))
        self.assertIsNone(rows[1].external_volume_kg)
        self.assertIsNone(rows[2].external_volume_kg)

        for invalid_fields in (
            {"load_type": "machine"},
            {"actual_kg": "12lb"},
            {"actual_kg": "-1"},
        ):
            invalid = self.client.post(
                f"/blocks/{block.pk}/sets/new/",
                {
                    "revision": 4,
                    "exercise": self.variant.pk,
                    "kind": "work",
                    "load_type": "external",
                    "side": "both",
                    **invalid_fields,
                },
            )
            self.assertEqual(invalid.status_code, 200)
            self.assertTrue(invalid.context["form"].errors)
        self.assertEqual(StrengthSet.objects.filter(block=block).count(), 3)
