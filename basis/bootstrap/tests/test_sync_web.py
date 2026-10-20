"""HTTP compatibility for existing IndexedDB queue bodies and session security."""

import json
from typing import cast
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import session_snapshot
from basis.modules.training.adapters.models import Block, Session


@override_settings(DEVELOPMENT_ACCESS=True)
class OfflineHTTPTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user("offline-http", password="test-password")
        self.profile = Athlete.objects.create(
            account=self.owner,
            nombre="Offline",
            email="offline@example.test",
            edad=25,
            fecha_inicio=timezone.localdate(),
            email_verified=True,
        )
        self.session = Session.objects.create(
            owner=self.owner, date=timezone.localdate(), title="Offline"
        )
        Block.objects.create(session=self.session, sport="running", title="Easy")
        self.client.force_login(self.owner)

    def body(self) -> dict[str, object]:
        return {
            "account": str(self.profile.public_id),
            "mutation_id": str(uuid4()),
            "created": 1792377600000,
            "session": session_snapshot(self.session),
        }

    def test_old_queue_body_replays_original_result_after_current_session_changes(self) -> None:
        body = self.body()
        first = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        Session.objects.filter(pk=self.session.pk).update(notes="later edit", revision=99)
        replay = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(SyncReceipt.objects.count(), 1)

    def test_queue_account_mismatch_has_original_scalar_error(self) -> None:
        body = self.body()
        body["account"] = str(uuid4())
        response = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "La cola pertenece a otra cuenta."})
        self.assertEqual(SyncReceipt.objects.count(), 0)

    def test_digest_mismatch_and_invalid_revision_have_original_detail_lists(self) -> None:
        body = self.body()
        self.assertEqual(
            self.client.post("/api/sync/", body, content_type="application/json").status_code, 200
        )
        payload = cast(dict[str, object], body["session"])
        payload["notes"] = "different"
        response = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            ["La misma operaci\u00f3n no puede contener datos diferentes."],
        )
        body["mutation_id"] = str(uuid4())
        payload["revision"] = True
        response = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], ["Formato o revisi\u00f3n de sesi\u00f3n inv\u00e1lida."]
        )

    def test_login_and_csrf_still_protect_mutations(self) -> None:
        self.client.logout()
        response = self.client.post("/api/sync/", self.body(), content_type="application/json")
        self.assertEqual(response.status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.owner)
        self.assertEqual(
            protected.post(
                "/api/sync/", json.dumps(self.body()), content_type="application/json"
            ).status_code,
            403,
        )
        self.assertEqual(SyncReceipt.objects.count(), 0)
