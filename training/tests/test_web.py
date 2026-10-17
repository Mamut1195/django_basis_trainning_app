import json
import re

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from training.models import Goal, Session
from training.proposals import build_plan

from .factories import account, proposal, session


class WebFlowTests(TestCase):
    def setUp(self):
        self.user = account()
        self.client.force_login(self.user)

    def test_primary_pages_and_forms_render(self):
        for path in (
            "/",
            "/plans/",
            "/progress/",
            "/profile/",
            "/billing/",
            "/coach/",
            "/offline/",
            "/plans/new/",
            "/sessions/new/",
            "/scheduled/new/",
            "/profile/edit/",
            "/profile/preferences/",
            "/records/goal/new/",
            "/records/sport/new/",
            "/records/wellness/new/",
            "/records/measurement/new/",
            "/records/trip/new/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_invalid_forms_show_errors_instead_of_raising(self):
        for path in ("/plans/new/", "/scheduled/new/", "/sessions/new/", "/records/goal/new/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, {"title": "Invalid"}).status_code, 200)

    def test_goal_plan_and_session_creation(self):
        response = self.client.post(
            "/records/goal/new/", {"title": "Correr", "sport": "running", "priority": "primary"}
        )
        self.assertEqual(response.status_code, 302)
        goal = Goal.objects.get(owner=self.user)
        date = timezone.localdate().isoformat()
        response = self.client.post(
            "/plans/new/", {"title": "Base", "goal": goal.pk, "start_date": date, "end_date": date}
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            "/sessions/new/",
            {
                "title": "Rodaje",
                "date": date,
                "duration_protocol": "elapsed",
                "block-sport": "running",
                "block-title": "Suave",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = Session.objects.get(owner=self.user)
        self.assertEqual(self.client.get(f"/sessions/{item.pk}/").status_code, 200)
        self.assertIsNone(item.reported_rpe)

    def test_scheduled_block_set_and_interval_forms_render(self):
        plan = build_plan(self.user, proposal(self.user))
        scheduled = plan.sessions.first()
        item = session(self.user, "strength")
        block = item.blocks.first()
        paths = [
            f"/plans/{plan.pk}/",
            f"/plans/{plan.pk}/cycles/new/",
            f"/scheduled/{scheduled.pk}/",
            f"/scheduled/{scheduled.pk}/reschedule/",
            f"/blocks/{block.pk}/sets/new/",
            f"/blocks/{scheduled.blocks.first().pk}/intervals/new/",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_public_offline_shell_has_no_private_account_data(self):
        self.client.logout()
        response = self.client.get("/offline/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, str(self.user.athlete.public_id))
        self.assertNotContains(response, self.user.email)

    def test_manifest_and_service_worker(self):
        manifest = self.client.get("/manifest.webmanifest").json()
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual({icon["sizes"] for icon in manifest["icons"]}, {"192x192", "512x512"})
        response = self.client.get("/service-worker.js")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "credentials:'omit'")

    def test_signup_requires_verification_then_login(self):
        self.client.logout()
        response = self.client.post(
            "/accounts/signup/",
            {
                "email": "new@example.test",
                "name": "Nueva",
                "adult": "on",
                "password1": "Long-Example-Pass-2026!",
                "password2": "Long-Example-Pass-2026!",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        path = re.search(r"http://127.0.0.1:8000([^\s]+)", mail.outbox[0].body).group(1)
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(username="new@example.test")
        self.assertFalse(user.is_active)
        self.assertEqual(self.client.get(path).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(self.client.post(path).status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.athlete.email_verified)
        self.assertTrue(
            self.client.login(username=user.username, password="Long-Example-Pass-2026!")
        )

    def test_sync_endpoint_rejects_malformed_json_and_wrong_account(self):
        self.assertEqual(
            self.client.post("/api/sync/", data="[]", content_type="application/json").status_code,
            400,
        )
        response = self.client.post(
            "/api/sync/",
            data=json.dumps({"account": "other", "session": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
