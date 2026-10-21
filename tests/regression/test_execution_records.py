"""MAM623 acceptance through real services, forms, receipts and source rows."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from typing import cast
from unittest.mock import patch
from uuid import UUID, uuid4

from django.db import connection
from django.http import HttpResponse
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from basis.bootstrap.manual_training import manual_training
from basis.modules.sync.adapters.actions import sync_session
from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.django import DjangoSessionRepository
from basis.modules.training.adapters.manual_repository import strength_data
from basis.modules.training.adapters.models import Block, Session, StrengthSet
from basis.modules.training.application.manual import SaveStrength
from basis.modules.training.domain.execution import StrengthData
from basis.modules.training.domain.manual import ManualInvalid
from basis.shared.identifiers import AccountId, BlockId, Revision, StrengthSetId

from .contracts import SessionDocument, build_plan, required, session_snapshot
from .factories import account, exercise, proposal


class ExecutionFixture:
    def make_prescription(self) -> None:
        self.owner = account("execution623")
        self.other = account("other623")
        self.exercise = exercise()
        self.variant = exercise()
        content = proposal(self.owner)
        content["sessions"][0]["blocks"] = [
            {
                "sport": "strength",
                "title": "Fuerza",
                "sets": [
                    {
                        "exercise": self.exercise.pk,
                        "target_reps": 5,
                        "target_kg": "80",
                        "tempo": "3-1-1-0",
                        "group": "A",
                    },
                    {"exercise": self.exercise.pk, "target_reps": 8, "target_kg": "60.25"},
                ],
            }
        ]
        self.plan = build_plan(self.owner, content)
        self.planned = self.plan.sessions.get()


class ExecutionRecordTests(ExecutionFixture, TestCase):
    def setUp(self) -> None:
        self.make_prescription()
        self.client.force_login(self.owner)

    def send(self, payload: object, key: UUID | None = None) -> HttpResponse:
        return cast(
            HttpResponse,
            self.client.post(
                "/api/sync/",
                {
                    "account": str(self.owner.athlete.public_id),
                    "mutation_id": str(key or uuid4()),
                    "session": payload,
                },
                content_type="application/json",
            ),
        )

    def test_two_daily_sessions_different_results_and_partial_closure(self) -> None:
        first = start_session(self.owner, self.planned)
        payload = session_snapshot(first)
        rows = payload["blocks"][0]["sets"]
        rows[0].update(actual_reps=4, actual_kg="75", actual_rpe="8")
        response = self.send({**payload, "status": "completed"})
        self.assertEqual(response.status_code, 200, response.content)
        source = required(self.planned.blocks.get().sets.first())
        actual = required(first.blocks.get().sets.first())
        pending = first.blocks.get().sets.all()[1]
        self.assertEqual(
            (actual.target_reps, actual.target_kg, actual.actual_reps, actual.actual_kg),
            (5, Decimal(80), 4, Decimal(75)),
        )
        self.assertEqual((pending.actual_reps, pending.actual_kg), (None, None))
        self.assertIsNone(source.actual_kg)
        self.assertEqual(actual.source_id, source.pk)
        self.assertEqual(actual.external_volume_kg, Decimal(300))
        self.assertIsNone(actual.estimated_1rm)
        second = {
            "id": str(uuid4()),
            "revision": 0,
            "date": first.date.isoformat(),
            "blocks": [
                {
                    "sport": "strength",
                    "title": "Otra",
                    "sets": [
                        {"exercise": self.exercise.pk, "actual_reps": 7, "actual_kg": "65.25"}
                    ],
                }
            ],
        }
        self.assertEqual(self.send(second).status_code, 200)
        self.assertEqual(Session.objects.filter(date=first.date).count(), 2)

    def test_start_and_new_sync_initialize_same_canonical_source(self) -> None:
        source = self.planned.blocks.get()
        payload: SessionDocument = {
            "id": str(uuid4()),
            "revision": 0,
            "planned": self.planned.pk,
            "blocks": [
                {
                    "sport": "strength",
                    "title": source.title,
                    "sets": [
                        {
                            "exercise": s.exercise_id,
                            "target_reps": s.target_reps,
                            "target_kg": str(s.target_kg),
                            "tempo": s.tempo,
                            "group": s.group,
                            "actual_reps": 4 if index == 0 else None,
                            "actual_kg": "75" if index == 0 else None,
                        }
                        for index, s in enumerate(source.sets.all())
                    ],
                }
            ],
        }
        response = self.send(payload)
        self.assertEqual(response.status_code, 200, response.content)
        stored = Session.objects.get(pk=payload["id"])
        self.assertEqual(stored.blocks.get().source_id, source.pk)
        self.assertEqual(
            list(stored.blocks.get().sets.values_list("source_id", flat=True)),
            list(source.sets.values_list("pk", flat=True)),
        )
        self.assertEqual(start_session(self.owner, self.planned).pk, stored.pk)

    def test_arbitrary_initial_or_existing_intention_rejected_atomically(self) -> None:
        bad = {
            "id": str(uuid4()),
            "revision": 0,
            "planned": self.planned.pk,
            "blocks": [
                {
                    "sport": "strength",
                    "title": "Fake",
                    "sets": [{"exercise": self.variant.pk, "target_reps": 99, "target_kg": "1.25"}],
                }
            ],
        }
        self.assertEqual(self.send(bad).status_code, 400)
        self.assertFalse(Session.objects.exists())
        self.assertFalse(SyncReceipt.objects.exists())
        item = start_session(self.owner, self.planned)
        before = session_snapshot(item)
        for key, value in (
            ("target_reps", 99),
            ("exercise", self.variant.pk),
            ("load_type", "assisted"),
            ("kind", "failed"),
            ("tempo", "x"),
            ("group", "B"),
        ):
            payload = deepcopy(before)
            payload["blocks"][0]["sets"][0][key] = value
            self.assertEqual(self.send(payload).status_code, 400, key)
            self.assertEqual(session_snapshot(item), before)

    def test_explicit_adaptation_preserves_original_and_requires_reason(self) -> None:
        item = start_session(self.owner, self.planned)
        payload = session_snapshot(item)
        row = payload["blocks"][0]["sets"][0]
        row.update(
            actual_exercise=self.variant.pk,
            actual_load_type="assisted",
            actual_kind="failed",
            actual_tempo="1-0-1-0",
            actual_group="B",
            actual_reps=0,
            actual_kg="75",
        )
        self.assertEqual(self.send(payload).status_code, 400)
        row["adaptation_reason"] = "Equipo no disponible; variante asistida"
        self.assertEqual(self.send(payload).status_code, 200)
        stored = required(item.blocks.get().sets.first())
        self.assertEqual(
            (stored.exercise_id, stored.kind, stored.load_type, stored.tempo, stored.group),
            (self.exercise.pk, "work", "external", "3-1-1-0", "A"),
        )
        self.assertEqual(stored.actual_exercise_id, self.variant.pk)
        self.assertEqual(stored.actual_reps, 0)
        self.assertIsNone(stored.external_volume_kg)
        self.assertEqual(stored.source_id, required(self.planned.blocks.get().sets.first()).pk)

    def test_manual_uses_same_intention_guard_and_adaptation(self) -> None:
        item = start_session(self.owner, self.planned)
        row = required(item.blocks.get().sets.first())
        data = strength_data(row)
        service = manual_training()

        def command(candidate: StrengthData) -> SaveStrength:
            return SaveStrength(
                AccountId(self.owner.pk),
                BlockId(row.block_id),
                Revision(1),
                candidate,
                StrengthSetId(row.pk),
            )

        with self.assertRaises(ManualInvalid):
            service.save_strength(command(replace(data, load_type="assisted")))
        service.save_strength(
            command(
                replace(
                    data,
                    actual_load_type="assisted",
                    adaptation_reason="Banda de asistencia",
                    actual_reps=4,
                )
            )
        )
        row.refresh_from_db()
        self.assertEqual(row.load_type, "external")
        self.assertEqual(row.actual_load_type, "assisted")

    def test_metadata_and_legacy_idless_snapshot_preserve_urls(self) -> None:
        item = start_session(self.owner, self.planned)
        block, row = item.blocks.get(), required(item.blocks.get().sets.first())
        block.order = 7
        block.save()
        for index, child in enumerate(block.sets.all(), 1):
            child.order = index * 5
            child.save()
        response = self.client.post(
            f"/sessions/{item.pk}/edit/",
            {
                "title": "Resumen",
                "date": item.date.isoformat(),
                "duration_protocol": "elapsed",
                "notes": "Solo notas",
                "revision": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(item.blocks.get().pk, block.pk)
        self.assertEqual(item.blocks.get().order, 7)
        self.assertEqual(list(item.blocks.get().sets.values_list("order", flat=True)), [5, 10])
        self.assertEqual(required(item.blocks.get().sets.first()).pk, row.pk)
        self.assertEqual(self.client.get(f"/sets/{row.pk}/edit/").status_code, 200)
        legacy = session_snapshot(item)
        for b in legacy["blocks"]:
            b.pop("id")
            b.pop("source")
            for s in b["sets"]:
                s.pop("id")
                s.pop("source")
                for key in list(s):
                    if key.startswith("actual_") and key not in (
                        "actual_kg",
                        "actual_reps",
                        "actual_rpe",
                        "actual_rir",
                        "actual_rest_seconds",
                    ):
                        s.pop(key)
                s.pop("adaptation_reason")
        self.assertEqual(self.send(legacy).status_code, 200)
        self.assertEqual(required(item.blocks.get().sets.first()).pk, row.pk)

    def test_foreign_and_wrong_parent_ids_are_generic_errors_without_changes(self) -> None:
        item = start_session(self.owner, self.planned)
        other_session = Session.objects.create(owner=self.owner, title="Otro")
        other_block = Block.objects.create(session=other_session, title="Otro", sport="strength")
        wrong = StrengthSet.objects.create(block=other_block, exercise=self.exercise)
        before = session_snapshot(item)
        for field, value in (("id", wrong.pk), ("source", wrong.pk)):
            payload = deepcopy(before)
            payload["blocks"][0]["sets"][0][field] = value
            self.assertEqual(self.send(payload).status_code, 400)
            self.assertEqual(session_snapshot(item), before)
        foreign = Session.objects.create(owner=self.other, title="Privada")
        foreign_block = Block.objects.create(session=foreign, title="Privado", sport="strength")
        payload = deepcopy(before)
        payload["blocks"][0]["id"] = foreign_block.pk
        self.assertEqual(self.send(payload).status_code, 400)
        self.assertFalse(SyncReceipt.objects.exists())

    def test_replay_keeps_original_ids_and_receipt_failure_rolls_back(self) -> None:
        item = start_session(self.owner, self.planned)
        payload, key = session_snapshot(item), uuid4()
        first = sync_session(self.owner, key, payload)
        self.assertEqual(sync_session(self.owner, key, payload), first)
        next_payload = session_snapshot(item)
        next_payload["blocks"][0]["sets"][0]["actual_reps"] = 4
        with patch(
            "basis.modules.sync.adapters.receipts.SyncReceipt.objects.create",
            side_effect=OSError("receipt"),
        ):
            with self.assertRaises(OSError):
                sync_session(self.owner, uuid4(), next_payload)
        self.assertEqual(session_snapshot(item), first)
        self.assertEqual(SyncReceipt.objects.count(), 1)

    def test_snapshot_read_queries_are_bounded_not_per_set(self) -> None:
        item = start_session(self.owner, self.planned)
        block = item.blocks.get()
        for _ in range(20):
            StrengthSet.objects.create(block=block, exercise=self.exercise)
        from basis.shared.identifiers import SessionId

        with CaptureQueriesContext(connection) as queries:
            state = DjangoSessionRepository().get(
                SessionId(UUID(str(item.pk))), lock=False, owner=AccountId(self.owner.pk)
            )
        self.assertEqual(len(required(state).blocks[0].sets), 22)
        self.assertLessEqual(len(queries), 6)

    def test_null_zero_invalid_numbers_and_no_implicit_deletion(self) -> None:
        item = start_session(self.owner, self.planned)
        payload = session_snapshot(item)
        payload["blocks"][0]["sets"][0].update(actual_reps=0, actual_kg="0")
        self.assertEqual(self.send(payload).status_code, 200)
        self.assertEqual(required(item.blocks.get().sets.first()).external_volume_kg, Decimal(0))
        before = session_snapshot(item)
        for invalid in (True, 4.5, "garbage", "NaN"):
            bad = deepcopy(before)
            bad["blocks"][0]["sets"][0]["actual_reps"] = invalid
            self.assertEqual(self.send(bad).status_code, 400)
        bad = deepcopy(before)
        bad["blocks"][0]["sets"][0]["actual_kg"] = "garbage"
        self.assertEqual(self.send(bad).status_code, 400)
        bad = deepcopy(before)
        bad["blocks"][0]["sets"].pop()
        self.assertEqual(self.send(bad).status_code, 400)
        self.assertEqual(session_snapshot(item), before)

    def test_existing_unplanned_execution_cannot_be_relabelled_as_prescribed(self) -> None:
        from .factories import session

        item = session(self.owner, "strength")
        before = session_snapshot(item)
        payload = deepcopy(before)
        payload["planned"] = self.planned.pk
        self.assertEqual(self.send(payload).status_code, 400)
        self.assertEqual(session_snapshot(item), before)

    def test_export_and_local_ai_context_keep_identity_state_and_provenance(self) -> None:
        from django.utils import timezone

        from basis.modules.training.adapters.coach import DjangoTrainingCoachContexts
        from basis.modules.training.adapters.export import DjangoTrainingExport

        item = start_session(self.owner, self.planned)
        payload = session_snapshot(item)
        payload["blocks"][0]["sets"][0].update(
            actual_exercise=self.variant.pk,
            adaptation_reason="Variante real",
            actual_reps=4,
            actual_kg="75",
        )
        self.assertEqual(self.send(payload).status_code, 200)
        row = required(item.blocks.get().sets.first())
        sections = DjangoTrainingExport().read(AccountId(self.owner.pk))
        exported = next(section for section in sections if section.key == "strengthset")
        fields = next(value for value in exported.rows if value["pk"] == row.pk)["fields"]
        assert isinstance(fields, dict)
        self.assertEqual(fields["source"], row.source_id)
        self.assertEqual(fields["actual_exercise"], self.variant.pk)
        self.assertEqual(fields["exercise"], self.exercise.pk)
        self.assertEqual(fields["adaptation_reason"], "Variante real")
        recent = (
            DjangoTrainingCoachContexts()
            .read(AccountId(self.owner.pk), timezone.localdate())
            .recent[0]
        )
        self.assertEqual(
            (recent.id, recent.status, recent.planned),
            (str(item.pk), "in_progress", self.planned.pk),
        )
        self.assertFalse(
            DjangoTrainingCoachContexts()
            .read(AccountId(self.other.pk), timezone.localdate())
            .recent
        )
