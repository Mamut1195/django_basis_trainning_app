"""Export-v1 remains stable across internal Django app-label changes."""

import json
from datetime import timedelta
from typing import cast

from django.contrib.auth.models import User as Account
from django.test import TestCase
from django.utils import timezone

from basis.modules.athletes.adapters.models import User
from basis.modules.training.adapters.models import Goal


class ExportCompatibilityTests(TestCase):
    def test_internal_app_reorganization_preserves_owner_and_external_model_tags(self) -> None:
        owner = Account.objects.create_user(username="export-owner", email="owner@example.test")
        stranger = Account.objects.create_user(
            username="export-stranger", email="stranger@example.test"
        )
        profile = User.objects.create(
            account=owner, nombre="Owner", email=owner.email, fecha_inicio=timezone.localdate()
        )
        User.objects.create(
            account=stranger,
            nombre="Stranger",
            email=stranger.email,
            fecha_inicio=timezone.localdate(),
        )
        day = timezone.localdate()
        Goal.objects.create(
            owner=owner, title="My goal", sport="running", target_date=day + timedelta(days=10)
        )
        Goal.objects.create(
            owner=stranger,
            title="Foreign goal",
            sport="running",
            target_date=day + timedelta(days=10),
        )
        self.client.force_login(owner)
        response = self.client.get("/export/")
        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, object], json.loads(response.content))
        self.assertEqual(payload["schema"], "basis-export-v1")
        athletes = cast(list[dict[str, object]], payload["athlete"])
        goals = cast(list[dict[str, object]], payload["goal"])
        self.assertEqual(
            [(row["model"], row["pk"]) for row in athletes],
            [("daily_trainning_app.user", profile.pk)],
        )
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["model"], "training.goal")
        self.assertEqual(cast(dict[str, object], goals[0]["fields"])["title"], "My goal")
        for resource, rows in payload.items():
            if resource in ("schema", "exported_at", "athlete"):
                continue
            expected = (
                "daily_trainning_app."
                if resource in ("workoutdata", "userexerciserm")
                else "training."
            ) + resource
            self.assertTrue(
                all(row["model"] == expected for row in cast(list[dict[str, object]], rows))
            )
