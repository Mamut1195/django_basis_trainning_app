"""Backend adaptation mutation regressions: omission is not a new observation."""

from copy import deepcopy
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from django.db import connection
from django.http import HttpResponse
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from basis.bootstrap.manual_training import manual_training
from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.manual_repository import strength_data
from basis.modules.training.adapters.models import StrengthSet
from basis.modules.training.application.manual import SaveStrength
from basis.modules.training.public import AdaptationField
from basis.shared.identifiers import AccountId, BlockId, Revision, StrengthSetId

from .contracts import SessionDocument, build_plan, required, session_snapshot, sync_session
from .factories import account, exercise, proposal

ADAPTATION_KEYS = (
    "actual_exercise",
    "actual_load_type",
    "actual_kind",
    "actual_tempo",
    "actual_range_of_motion",
    "actual_side",
    "actual_group",
    "adaptation_reason",
)


class BackendAdaptationFixture:
    def make_adapted(self) -> None:
        self.owner, self.other = account("backend623"), account("other-backend623")
        self.exercise, self.variant = exercise(), exercise()
        content = proposal(self.owner)
        content["sessions"][0]["blocks"] = [
            {
                "sport": "strength",
                "title": "Original",
                "sets": [
                    {"exercise": self.exercise.pk, "target_reps": 5, "target_kg": "80"},
                    {"exercise": self.exercise.pk, "target_reps": 8, "target_kg": "60"},
                ],
            }
        ]
        self.plan = build_plan(self.owner, content)
        self.item = start_session(self.owner, self.plan.sessions.get())
        self.row = required(self.item.blocks.get().sets.first())
        cast(TestCase, self).client.force_login(self.owner)
        payload = session_snapshot(self.item)
        payload["blocks"][0]["sets"][0].update(
            actual_exercise=self.variant.pk,
            actual_load_type="assisted",
            actual_kind="failed",
            actual_reps=4,
            actual_kg="75",
            actual_rpe="10",
            adaptation_reason="Observed assistance",
        )
        response = self.send(payload)
        cast(TestCase, self).assertEqual(response.status_code, 200, response.content)
        self.row.refresh_from_db()

    def send(self, payload: object, key: UUID | None = None) -> HttpResponse:
        return cast(
            HttpResponse,
            cast(TestCase, self).client.post(
                "/api/sync/",
                {
                    "account": str(self.owner.athlete.public_id),
                    "mutation_id": str(key or uuid4()),
                    "session": payload,
                },
                content_type="application/json",
            ),
        )


class BackendAdaptationUpdates(BackendAdaptationFixture, TestCase):
    def setUp(self) -> None:
        self.make_adapted()

    def test_current_legacy_notes_keep_observation_and_metrics(self) -> None:
        self.assertIsNone(self.row.external_volume_kg)
        self.assertIsNone(self.row.estimated_1rm)
        before = self.row.pk, self.row.block_id, self.row.source_id
        payload = deepcopy(session_snapshot(self.item))
        payload["notes"] = "Legacy notes only, current revision"
        for block in payload["blocks"]:
            block.pop("id", None)
            block.pop("source", None)
            for row in block["sets"]:
                row.pop("id", None)
                row.pop("source", None)
                for field in ADAPTATION_KEYS:
                    row.pop(field, None)
        before_intent = tuple(
            getattr(self.row, name)
            for name in (
                "exercise_id",
                "kind",
                "load_type",
                "tempo",
                "range_of_motion",
                "side",
                "group",
                "rest_seconds",
                "rm_reference_id",
                "target_reps",
                "target_reps_min",
                "target_reps_max",
                "target_kg",
                "target_percent_rm",
                "target_rpe",
                "target_rir",
                "target_isometric_seconds",
            )
        )
        with CaptureQueriesContext(connection) as queries:
            response = self.send(payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.row.refresh_from_db()
        self.assertEqual((self.row.pk, self.row.block_id, self.row.source_id), before)
        self.assertEqual(
            (
                self.row.actual_exercise_id,
                self.row.actual_load_type,
                self.row.actual_kind,
                self.row.adaptation_reason,
            ),
            (self.variant.pk, "assisted", "failed", "Observed assistance"),
        )
        self.assertIsNone(self.row.external_volume_kg)
        self.assertIsNone(self.row.estimated_1rm)
        self.assertEqual(
            (self.row.target_reps, self.row.target_kg, self.row.actual_reps, self.row.actual_kg),
            (5, Decimal(80), 4, Decimal(75)),
        )
        self.assertEqual(SyncReceipt.objects.count(), 2)
        self.assertEqual(
            tuple(
                getattr(self.row, name)
                for name in (
                    "exercise_id",
                    "kind",
                    "load_type",
                    "tempo",
                    "range_of_motion",
                    "side",
                    "group",
                    "rest_seconds",
                    "rm_reference_id",
                    "target_reps",
                    "target_reps_min",
                    "target_reps_max",
                    "target_kg",
                    "target_percent_rm",
                    "target_rpe",
                    "target_rir",
                    "target_isometric_seconds",
                )
            ),
            before_intent,
        )
        self.assertFalse(
            any(
                query["sql"]
                .lstrip()
                .upper()
                .startswith(
                    (
                        'UPDATE "BASIS_TRAINING_STRENGTHSET"',
                        'DELETE FROM "BASIS_TRAINING_STRENGTHSET"',
                        'INSERT INTO "BASIS_TRAINING_STRENGTHSET"',
                        'UPDATE "BASIS_TRAINING_BLOCK"',
                    )
                )
                for query in queries
            )
        )

    def test_explicit_row_identity_from_another_parent_never_maps_to_an_omitted_patch(self) -> None:
        from basis.modules.training.adapters.models import Block, Session

        before, receipts = session_snapshot(self.item), SyncReceipt.objects.count()
        responses = []
        for actor in (self.owner, self.other):
            other_session = Session.objects.create(owner=actor, title="Private other parent")
            block = Block.objects.create(session=other_session, title="Other", sport="strength")
            foreign_row = StrengthSet.objects.create(block=block, exercise=self.exercise)
            payload = deepcopy(before)
            row = payload["blocks"][0]["sets"][0]
            for key in ADAPTATION_KEYS:
                row.pop(key, None)
            row["id"] = foreign_row.pk
            response = self.send(payload)
            self.assertEqual(response.status_code, 400)
            responses.append(response.content)
            self.assertEqual(session_snapshot(self.item), before)
            self.assertEqual(SyncReceipt.objects.count(), receipts)
        self.assertEqual(responses[0], responses[1])

    def test_numeric_only_current_edit_preserves_classification_reason_and_nulls(self) -> None:
        payload = session_snapshot(self.item)
        changed = payload["blocks"][0]["sets"][0]
        for field in ADAPTATION_KEYS:
            changed.pop(field, None)
        changed.update(actual_reps=0, actual_kg=None, actual_rpe=None)
        self.assertEqual(self.send(payload).status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(
            (self.row.actual_reps, self.row.actual_kg, self.row.actual_rpe), (0, None, None)
        )
        self.assertEqual(
            (self.row.actual_load_type, self.row.actual_kind, self.row.adaptation_reason),
            ("assisted", "failed", "Observed assistance"),
        )
        self.assertIsNone(self.row.external_volume_kg)
        self.assertIsNone(self.row.estimated_1rm)

    def test_reclassification_requires_reason_in_this_change_not_implicit_inheritance(self) -> None:
        before, receipts = session_snapshot(self.item), SyncReceipt.objects.count()
        for reason in (
            None,
            "",
            "  ",
        ):
            payload = deepcopy(before)
            row = payload["blocks"][0]["sets"][0]
            row["actual_kind"] = "work"
            row.pop("adaptation_reason", None)
            if reason is not None:
                row["adaptation_reason"] = reason
            self.assertEqual(self.send(payload).status_code, 400)
            self.assertEqual(session_snapshot(self.item), before)
            self.assertEqual(SyncReceipt.objects.count(), receipts)

    def test_explicit_same_reason_accepts_and_records_each_override_change(self) -> None:
        before = session_snapshot(self.item)
        source_id, row_id = self.row.source_id, self.row.pk
        payload = deepcopy(before)
        row = payload["blocks"][0]["sets"][0]
        for field in ADAPTATION_KEYS:
            row.pop(field, None)
        row.update(actual_kind="work", adaptation_reason="Observed assistance")
        key = uuid4()
        response = self.send(payload, key)
        self.assertEqual(response.status_code, 200, response.content)
        self.row.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.item.revision, before["revision"] + 1)
        self.assertEqual(
            (self.row.actual_kind, self.row.adaptation_reason), ("work", "Observed assistance")
        )
        self.assertEqual(
            (self.row.pk, self.row.source_id, self.row.kind, self.row.target_kg),
            (row_id, source_id, "work", Decimal(80)),
        )
        recorded = sync_session(self.owner, key, payload)
        self.assertEqual(recorded["blocks"][0]["sets"][0]["actual_kind"], "work")
        self.assertEqual(
            recorded["blocks"][0]["sets"][0]["adaptation_reason"], "Observed assistance"
        )
        next_payload = session_snapshot(self.item)
        next_payload["blocks"][0]["sets"][0].update(
            actual_kind="failed", adaptation_reason=" observed ASSISTANCE "
        )
        self.assertEqual(self.send(next_payload).status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(
            (self.row.actual_kind, self.row.adaptation_reason), ("failed", " observed ASSISTANCE ")
        )
        self.assertEqual(SyncReceipt.objects.count(), 3)
        self.assertEqual(sync_session(self.owner, key, payload), recorded)

    def test_partial_adaptation_merges_omitted_fields_with_new_reason(self) -> None:
        payload = session_snapshot(self.item)
        row = payload["blocks"][0]["sets"][0]
        for key in ADAPTATION_KEYS:
            row.pop(key, None)
        row.update(
            actual_kind="warmup", adaptation_reason="Nueva observación: calentamiento asistido"
        )
        self.assertEqual(self.send(payload).status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(
            (self.row.actual_exercise_id, self.row.actual_load_type, self.row.actual_kind),
            (self.variant.pk, "assisted", "warmup"),
        )
        self.assertIsNone(self.row.external_volume_kg)
        self.assertEqual(
            (self.row.kind, self.row.load_type, self.row.exercise_id),
            ("work", "external", self.exercise.pk),
        )

    def test_null_or_empty_cannot_clear_observation_even_with_new_reason(self) -> None:
        before, receipts = session_snapshot(self.item), SyncReceipt.objects.count()
        for key in ("actual_exercise", "actual_load_type", "actual_kind", "adaptation_reason"):
            for value in (None, ""):
                payload = deepcopy(before)
                row = payload["blocks"][0]["sets"][0]
                row["adaptation_reason"] = "Motivo nuevo no autoriza borrar datos"
                row[key] = value
                self.assertEqual(self.send(payload).status_code, 400, key)
                self.assertEqual(session_snapshot(self.item), before)
                self.assertEqual(SyncReceipt.objects.count(), receipts)
        payload = deepcopy(before)
        row = payload["blocks"][0]["sets"][0]
        for key in ADAPTATION_KEYS[:-1]:
            row[key] = None
        row["adaptation_reason"] = "Borrado deliberado no soportado"
        self.assertEqual(self.send(payload).status_code, 400)
        self.assertEqual(session_snapshot(self.item), before)

    def test_return_to_prescribed_values_is_an_explicit_observation_and_old_replay_survives(
        self,
    ) -> None:
        original = session_snapshot(self.item)
        old_key = uuid4()
        old_result = sync_session(self.owner, old_key, original)
        current = session_snapshot(self.item)
        current["blocks"][0]["sets"][0].update(
            actual_exercise=self.exercise.pk,
            actual_load_type="external",
            actual_kind="work",
            adaptation_reason="Nueva observación sin asistencia, ejercicio original",
        )
        self.assertEqual(self.send(current).status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.external_volume_kg, Decimal("300.00"))
        self.assertEqual(self.row.estimated_1rm, Decimal("85.00"))
        self.assertEqual(sync_session(self.owner, old_key, original), old_result)
        self.assertEqual(old_result["blocks"][0]["sets"][0]["actual_load_type"], "assisted")
        self.assertEqual((self.row.target_reps, self.row.target_kg), (5, Decimal(80)))

    def test_manual_numeric_post_omission_preserves_observation(self) -> None:
        response = self.client.post(
            f"/sets/{self.row.pk}/edit/",
            {"revision": 2, "actual_reps": 4, "actual_kg": "75", "actual_rpe": "10"},
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.row.refresh_from_db()
        self.assertEqual(
            (
                self.row.actual_exercise_id,
                self.row.actual_load_type,
                self.row.actual_kind,
                self.row.adaptation_reason,
            ),
            (self.variant.pk, "assisted", "failed", "Observed assistance"),
        )
        self.assertIsNone(self.row.external_volume_kg)
        self.assertIsNone(self.row.estimated_1rm)

    def test_manual_port_uses_same_typed_presence_and_reason_guard(self) -> None:
        from dataclasses import replace

        from basis.modules.training.domain.manual import ManualInvalid

        data = strength_data(self.row)
        absent = replace(
            data,
            actual_exercise=None,
            actual_load_type=None,
            actual_kind=None,
            adaptation_reason="",
            actual_reps=0,
        )
        service = manual_training()
        command = SaveStrength(
            AccountId(self.owner.pk),
            BlockId(self.row.block_id),
            Revision(2),
            absent,
            StrengthSetId(self.row.pk),
            frozenset(),
        )
        service.save_strength(command)
        self.row.refresh_from_db()
        self.assertEqual(self.row.actual_load_type, "assisted")

        self.assertEqual(self.row.actual_reps, 0)
        changed = replace(strength_data(self.row), actual_load_type="external")
        with self.assertRaises(ManualInvalid):
            service.save_strength(
                replace(
                    command,
                    revision=Revision(3),
                    data=changed,
                    provided_adaptation=frozenset({AdaptationField.LOAD_TYPE}),
                )
            )
        self.row.refresh_from_db()
        self.assertEqual(self.row.actual_load_type, "assisted")

        service.save_strength(
            replace(
                command,
                revision=Revision(3),
                data=changed,
                provided_adaptation=frozenset({AdaptationField.LOAD_TYPE, AdaptationField.REASON}),
            )
        )
        self.row.refresh_from_db()
        self.assertEqual(self.row.actual_load_type, "external")
        self.assertEqual(self.row.adaptation_reason, "Observed assistance")

    def test_unchanged_full_snapshot_is_not_a_reclassification(self) -> None:
        current = session_snapshot(self.item)
        self.assertEqual(self.send(current).status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.adaptation_reason, "Observed assistance")
        self.assertIsNone(self.row.external_volume_kg)

    def test_stale_or_foreign_or_malformed_mutations_do_not_advance_or_create_receipts(
        self,
    ) -> None:
        before = session_snapshot(self.item)
        receipts = SyncReceipt.objects.count()
        stale = deepcopy(before)
        stale["revision"] = 1
        stale["blocks"][0]["sets"][0]["actual_kind"] = "work"
        self.assertEqual(self.send(stale).status_code, 409)
        for field, value in (
            ("actual_kind", True),
            ("actual_tempo", 13),
            ("actual_exercise", True),
            ("adaptation_reason", ["text"]),
            ("adaptation_presence", []),
        ):
            malformed = deepcopy(before)
            malformed["blocks"][0]["sets"][0][field] = value
            self.assertEqual(self.send(malformed).status_code, 400)
        self.client.force_login(self.other)
        foreign = self.client.post(
            "/api/sync/",
            {
                "account": str(self.other.athlete.public_id),
                "mutation_id": str(uuid4()),
                "session": before,
            },
            content_type="application/json",
        )
        self.assertEqual(foreign.status_code, 400)
        self.assertEqual(session_snapshot(self.item), before)
        self.assertEqual(SyncReceipt.objects.count(), receipts)

    def test_new_creation_absent_adaptation_is_normal_and_receipt_failure_rolls_back(self) -> None:
        from unittest.mock import patch

        payload: SessionDocument = {
            "id": str(uuid4()),
            "revision": 0,
            "title": "Sin adaptación",
            "blocks": [
                {
                    "sport": "strength",
                    "title": "Real",
                    "sets": [{"exercise": self.exercise.pk, "actual_reps": 0, "actual_kg": "0"}],
                }
            ],
        }
        self.assertEqual(self.send(payload).status_code, 200)
        row = StrengthSet.objects.get(block__session_id=payload["id"])
        self.assertIsNone(row.actual_load_type)
        self.assertEqual(row.external_volume_kg, Decimal(0))
        before = session_snapshot(self.item)
        receipts = SyncReceipt.objects.count()
        changed = deepcopy(before)
        changed["blocks"][0]["sets"][0].update(
            actual_kind="work", adaptation_reason="Nueva observación que debe revertirse"
        )
        with patch(
            "basis.modules.sync.adapters.receipts.SyncReceipt.objects.create",
            side_effect=OSError("receipt write"),
        ):
            with self.assertRaises(OSError):
                sync_session(self.owner, uuid4(), changed)
        self.assertEqual(session_snapshot(self.item), before)
        self.assertEqual(SyncReceipt.objects.count(), receipts)

    def test_new_linked_strength_creation_with_absent_adaptation_is_normal(self) -> None:
        content = proposal(self.owner)
        content["sessions"][0]["blocks"] = [
            {
                "sport": "strength",
                "title": "New canonical",
                "sets": [{"exercise": self.exercise.pk, "target_reps": 5, "target_kg": "80"}],
            }
        ]
        plan = build_plan(self.owner, content)
        payload: SessionDocument = {
            "id": str(uuid4()),
            "revision": 0,
            "planned": plan.sessions.get().pk,
            "blocks": [
                {
                    "sport": "strength",
                    "title": "New canonical",
                    "sets": [
                        {
                            "exercise": self.exercise.pk,
                            "target_reps": 5,
                            "target_kg": "80",
                            "actual_reps": 0,
                            "actual_kg": "0",
                        }
                    ],
                }
            ],
        }
        response = self.send(payload)
        self.assertEqual(response.status_code, 200, response.content)
        row = StrengthSet.objects.get(block__session_id=payload["id"])
        self.assertIsNotNone(row.source_id)
        self.assertEqual(
            (row.actual_load_type, row.actual_kind, row.adaptation_reason), (None, None, "")
        )
        self.assertEqual(row.external_volume_kg, Decimal(0))

    def test_rejected_clear_does_not_change_budget_or_quota_rows(self) -> None:
        from basis.modules.coach.adapters.models import AIJob, UsagePeriod

        before_usage = list(UsagePeriod.objects.values())
        before_jobs = AIJob.objects.count()
        current = session_snapshot(self.item)
        current["blocks"][0]["sets"][0].update(actual_load_type=None, adaptation_reason="No borrar")
        self.assertEqual(self.send(current).status_code, 400)
        self.assertEqual(list(UsagePeriod.objects.values()), before_usage)
        self.assertEqual(AIJob.objects.count(), before_jobs)
