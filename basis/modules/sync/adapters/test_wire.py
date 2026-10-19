"""Exact canonical hashing and persisted snapshot round trips at the boundary."""

import hashlib
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from basis.bootstrap.sync import changes, decode_snapshot, encode_session
from basis.modules.training.public import (
    BlockData,
    IntervalData,
    Metric,
    MetricName,
    SessionState,
    StrengthData,
)
from basis.shared.identifiers import AccountId, Revision, SessionId

from .wire import WireSource


class OfflineWireTests(SimpleTestCase):
    def test_digest_uses_original_unicode_and_numeric_representations(self) -> None:
        payload: dict[str, object] = {
            "id": str(uuid4()), "revision": 0, "notes": "caf\u00e9", "blocks": None,
        }
        mutation = uuid4()
        source = WireSource(mutation, payload, AccountId(1), changes)
        expected = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        self.assertEqual(source.identity().digest, expected)
        self.assertEqual(source.identity().digest, WireSource(
            mutation, dict(reversed(tuple(payload.items()))), AccountId(1), changes
        ).identity().digest)
        numeric = dict(payload, duration_seconds=0)
        floating = dict(payload, duration_seconds=0.0)
        self.assertNotEqual(
            WireSource(mutation, numeric, AccountId(1), changes).identity().digest,
            WireSource(mutation, floating, AccountId(1), changes).identity().digest,
        )

    def test_identity_does_not_eagerly_decode_revision_shape_or_changes(self) -> None:
        payload = {"id": str(uuid4()), "revision": True, "blocks": "bad", "extra": 1}
        source = WireSource(uuid4(), payload, AccountId(1), changes)
        source.identity()
        with self.assertRaisesMessage(ValidationError, "Formato o revisi\u00f3n"):
            source.revision()

    def test_invalid_identifiers_have_original_validation_error(self) -> None:
        for mutation, payload in (("bad", {}), (uuid4(), {}), (uuid4(), {"id": "bad"})):
            with self.assertRaisesMessage(ValidationError, "Identificador de sincronizaci\u00f3n"):
                WireSource(mutation, payload, AccountId(1), changes).identity()

    def test_snapshot_codec_preserves_child_ids_order_scales_null_and_zero(self) -> None:
        initial = SessionState(
            SessionId(uuid4()), AccountId(4), date(2026, 10, 19), revision=Revision(7),
            duration_seconds=0, reported_rpe=Decimal("0.00"),
            blocks=(
                BlockData("strength", id=93, order=9, sets=(
                    StrengthData(12, target_kg=Decimal("50.000"), actual_reps=0),
                )),
                BlockData("running", id=28, order=3, target=(
                    Metric(MetricName.DISTANCE_M, Decimal("123.4500")),
                ), intervals=(IntervalData(actual_rpe=Decimal("0.00")),)),
            ),
        )
        snapshot = encode_session(initial)
        self.assertEqual(encode_session(decode_snapshot(initial.owner, snapshot)), snapshot)
        self.assertEqual(decode_snapshot(initial.owner, snapshot), initial)
        self.assertEqual(decode_snapshot(AccountId(8), snapshot), replace(initial, owner=AccountId(8)))
