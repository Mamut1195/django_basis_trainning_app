"""BASIS-002 acceptance matrix against actual session-authenticated endpoints."""

import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from daily_trainning_app.models import User as Athlete
from daily_trainning_app.models import UserExerciseRM, WorkoutData
from training.ai import context_snapshot
from training.models import Goal

from .factories import account, exercise, session


class PrivateAccessTests(TestCase):
    def setUp(self):
        self.owner, self.other = account("owner"), account("other")
        self.exercise = exercise()
        self.date = timezone.localdate().isoformat()
        self.client = APIClient()
        self.records = {}
        for user in (self.owner, self.other):
            self.records[user.pk] = {
                "workout-data": WorkoutData.objects.create(
                    user=user.athlete,
                    exercise=self.exercise,
                    fecha=self.date,
                    sets=1,
                    reps=5,
                    peso=40,
                ),
                "user-exercise-rm": UserExerciseRM.objects.create(
                    user=user.athlete,
                    exercise=self.exercise,
                    fecha_registro=self.date,
                    peso_maximo_rm=100,
                ),
            }

    def payload(self, resource):
        if resource == "workout-data":
            return {
                "exercise_id": self.exercise.pk,
                "fecha": self.date,
                "sets": 2,
                "reps": 5,
                "peso": "42.25",
            }
        return {
            "exercise_id": self.exercise.pk,
            "fecha_registro": self.date,
            "peso_maximo_rm": "105.25",
        }

    def test_anonymous_record_matrix(self):
        for resource, row in self.records[self.owner.pk].items():
            path = f"/api/v1/{resource}/"
            for method, url in (
                ("get", path),
                ("post", path),
                ("get", f"{path}{row.pk}/"),
                ("patch", f"{path}{row.pk}/"),
                ("delete", f"{path}{row.pk}/"),
            ):
                with self.subTest(resource=resource, method=method, url=url):
                    response = getattr(self.client, method)(url, self.payload(resource))
                    self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/v1/workout-data/latest/").status_code, 403)
        self.assertEqual(WorkoutData.objects.count(), 2)
        self.assertEqual(UserExerciseRM.objects.count(), 2)

    def test_both_accounts_list_and_retrieve_only_their_own_records(self):
        for user, other in ((self.owner, self.other), (self.other, self.owner)):
            self.client.force_login(user)
            for resource, row in self.records[user.pk].items():
                with self.subTest(user=user.pk, resource=resource):
                    path = f"/api/v1/{resource}/"
                    own = self.client.get(f"{path}{row.pk}/")
                    self.assertEqual(own.status_code, 200)
                    self.assertEqual(own.json()["user"], user.athlete.pk)
                    result = self.client.get(path).json()
                    self.assertEqual([r["id"] for r in result["results"]], [row.pk])
                    foreign = self.records[other.pk][resource]
                    for method in ("get", "patch", "delete"):
                        response = getattr(self.client, method)(
                            f"{path}{foreign.pk}/", self.payload(resource)
                        )
                        self.assertEqual(response.status_code, 404)

    def test_latest_is_scoped_even_when_foreign_record_is_newer(self):
        self.client.force_login(self.owner)
        response = self.client.get("/api/v1/workout-data/latest/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.records[self.owner.pk]["workout-data"].pk)
        self.records[self.owner.pk]["workout-data"].delete()
        empty = self.client.get("/api/v1/workout-data/latest/")
        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.data)

    def test_create_both_record_types_assigns_profile_not_auth_id(self):
        # Deliberately create different account/profile primary keys.
        get_user_model().objects.create_user(username="unlinked")
        user = account("offset")
        self.assertNotEqual(user.pk, user.athlete.pk)
        self.client.force_login(user)
        for resource, model in (
            ("workout-data", WorkoutData),
            ("user-exercise-rm", UserExerciseRM),
        ):
            response = self.client.post(f"/api/v1/{resource}/", self.payload(resource))
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(model.objects.get(pk=response.json()["id"]).user_id, user.athlete.pk)

    def test_foreign_profile_references_rejected_on_create_and_patch(self):
        self.client.force_login(self.owner)
        for resource, row in self.records[self.owner.pk].items():
            path = f"/api/v1/{resource}/"
            data = {**self.payload(resource), "user_id": self.other.athlete.pk}
            self.assertEqual(self.client.post(path, data).status_code, 400)
            self.assertEqual(self.client.patch(f"{path}{row.pk}/", data).status_code, 400)
            row.refresh_from_db()
            self.assertEqual(row.user_id, self.owner.athlete.pk)

    def test_nested_readonly_profile_cannot_reassign_owner(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            "/api/v1/workout-data/",
            {
                **self.payload("workout-data"),
                "user": {"id": self.other.athlete.pk, "account": self.other.pk},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            WorkoutData.objects.get(pk=response.json()["id"]).user_id, self.owner.athlete.pk
        )

    def test_record_responses_do_not_repeat_personal_profile(self):
        self.client.force_login(self.owner)
        for resource, row in self.records[self.owner.pk].items():
            for path in (f"/api/v1/{resource}/", f"/api/v1/{resource}/{row.pk}/"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                text = response.content.decode()
                for key in ("email", "ciudad", "edad", "objetivos"):
                    self.assertNotIn(f'"{key}"', text)
                rows = response.json().get("results", [response.json()])
                self.assertTrue(all(row["user"] == self.owner.athlete.pk for row in rows))
                self.assertNotIn(self.other.email, text)
        profile = self.client.get("/api/v1/users/").json()["results"]
        self.assertEqual([row["id"] for row in profile], [self.owner.athlete.pk])

    def test_authenticated_without_profile_cannot_read_legacy_or_create(self):
        user = get_user_model().objects.create_user(username="no-profile")
        self.client.force_login(user)
        for resource in ("users", "workout-data", "user-exercise-rm"):
            self.assertEqual(self.client.get(f"/api/v1/{resource}/").json()["count"], 0)
        for resource in ("workout-data", "user-exercise-rm"):
            self.assertEqual(
                self.client.post(f"/api/v1/{resource}/", self.payload(resource)).status_code, 403
            )

    def test_session_authenticated_record_writes_require_real_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for resource in ("workout-data", "user-exercise-rm"):
            self.assertEqual(
                client.post(f"/api/v1/{resource}/", self.payload(resource)).status_code, 403
            )
        self.assertEqual(client.get("/api/csrf/").status_code, 200)
        token = client.cookies["csrftoken"].value
        for resource in ("workout-data", "user-exercise-rm"):
            response = client.post(
                f"/api/v1/{resource}/", self.payload(resource), HTTP_X_CSRFTOKEN=token
            )
            self.assertEqual(response.status_code, 201, response.content)

    def test_html_export_and_ai_context_do_not_include_other_account(self):
        other_session = session(self.other)
        other_session.title = "Foreign private session"
        other_session.save(update_fields=["title"])
        Goal.objects.create(owner=self.other, title="Foreign private goal", sport="running")
        for path in ("/", "/profile/", "/progress/", "/export/", "/coach/"):
            self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.owner)
        for path in ("/", "/profile/", "/progress/", "/export/", "/coach/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Foreign private")
            self.assertNotContains(response, self.other.email)
        for path in (
            f"/sessions/{other_session.pk}/",
            f"/api/sessions/{other_session.pk}/snapshot/",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)
        exported = self.client.get("/export/").json()
        self.assertEqual(
            [row["pk"] for row in exported["workoutdata"]],
            [self.records[self.owner.pk]["workout-data"].pk],
        )
        snapshot = json.dumps(context_snapshot(self.owner), default=str)
        self.assertNotIn("Foreign private", snapshot)
        self.assertNotIn(self.other.email, snapshot)


class ExplicitLegacyLinkTests(TestCase):
    def setUp(self):
        self.account = get_user_model().objects.create_user(
            username="legacy", email="legacy@example.test"
        )
        self.profile = Athlete.objects.create(
            nombre="Legacy", email=self.account.email, fecha_inicio=timezone.localdate()
        )

    def link(self, account_id=None, profile_id=None):
        call_command(
            "link_legacy_profile",
            account_id=account_id or self.account.pk,
            profile_id=profile_id or self.profile.pk,
            stdout=StringIO(),
        )

    def test_matching_ids_and_email_do_not_automatically_assign_profile(self):
        self.assertEqual(self.profile.pk, self.account.pk)
        self.assertIsNone(self.profile.account_id)
        self.link()
        self.link()  # Explicit linking to the same account is idempotent.
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.account_id, self.account.pk)
        self.assertFalse(self.profile.email_verified)

    def test_cannot_steal_a_linked_profile(self):
        self.link()
        stranger = get_user_model().objects.create_user(
            username="stranger", email=self.account.email
        )
        with self.assertRaises(CommandError):
            self.link(account_id=stranger.pk)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.account_id, self.account.pk)

    def test_different_emails_require_operator_review(self):
        self.account.email = "different@example.test"
        self.account.save(update_fields=["email"])
        with self.assertRaises(CommandError):
            self.link()
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.account_id)

    def test_existing_profile_is_never_merged(self):
        Athlete.objects.create(
            account=self.account,
            nombre="Existing",
            email="existing@example.test",
            fecha_inicio=timezone.localdate(),
        )
        with self.assertRaises(CommandError):
            self.link()
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.account_id)
