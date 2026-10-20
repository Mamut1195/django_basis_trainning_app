"""Install the final seven-module schema on the test runner's disposable database."""

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import get_commands, load_command_class
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase

MODEL_OWNERS: dict[str, tuple[str, ...]] = {
    "accounts": ("RateWindow",),
    "athletes": ("User", "AthleteSettings", "SportProfile", "Measurement", "Wellness", "UserExerciseRM", "WorkoutData"),
    "catalog": ("Classification", "Exercise"),
    "training": ("Goal", "TrainingPlan", "Cycle", "PlannedSession", "Session", "Block", "StrengthSet", "Interval", "TrekTrip", "TrekStage"),
    "billing": ("BillingAccount", "WebhookReceipt"),
    "coach": ("UsagePeriod", "TrialFund", "AIJob", "PlanProposal", "AIServiceState"),
    "sync": ("SyncReceipt",),
}


class FinalInstallationTests(TestCase):
    def test_all_concrete_models_have_their_final_module_owner(self) -> None:
        self.assertEqual(sum(map(len, MODEL_OWNERS.values())), 28)
        self.assertFalse(apps.is_installed("daily_trainning_app"))
        self.assertFalse(apps.is_installed("training"))
        for area, expected in MODEL_OWNERS.items():
            with self.subTest(area=area):
                config = apps.get_app_config("basis_" + area)
                self.assertEqual(config.name, "basis.modules." + area + ".adapters")
                self.assertEqual({model.__name__ for model in config.get_models()}, set(expected))
                for model in config.get_models():
                    self.assertEqual(model.__module__, config.name + ".models")

    def test_fresh_database_contains_final_tables_and_applied_initial_migrations(self) -> None:
        tables = set(connection.introspection.table_names())
        self.assertFalse({name for name in tables if name.startswith(("daily_trainning_app_", "training_"))})
        applied = MigrationRecorder(connection).applied_migrations()
        for area in MODEL_OWNERS:
            label = "basis_" + area
            with self.subTest(app=label):
                self.assertIn((label, "0001_initial"), applied)
                for model in apps.get_app_config(label).get_models():
                    self.assertIn(model._meta.db_table, tables)

    def test_content_types_and_authorization_permissions_use_final_labels(self) -> None:
        for area in MODEL_OWNERS:
            label = "basis_" + area
            for model in apps.get_app_config(label).get_models():
                with self.subTest(model=model._meta.label):
                    model_name = model._meta.model_name
                    assert model_name is not None
                    content_type = ContentType.objects.get(app_label=label, model=model_name)
                    actual = set(Permission.objects.filter(content_type=content_type).values_list("codename", flat=True))
                    expected = {action + "_" + model_name for action in model._meta.default_permissions}
                    self.assertTrue(expected.issubset(actual))
        self.assertFalse(ContentType.objects.filter(app_label__in=("daily_trainning_app", "training")).exists())

    def test_operational_commands_are_registered_in_final_modules(self) -> None:
        commands = get_commands()
        expected = {
            "link_legacy_profile": "basis.modules.accounts.adapters",
            "seed_demo": "basis.modules.accounts.adapters",
            "process_ai_jobs": "basis.modules.coach.adapters",
            "reconcile_billing": "basis.modules.billing.adapters",
        }
        for name, app_name in expected.items():
            with self.subTest(command=name):
                self.assertEqual(commands[name], app_name)
                command = load_command_class(app_name, name)
                parser = command.create_parser("manage.py", name)
                self.assertEqual(parser.prog, "manage.py " + name)
