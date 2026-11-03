from uuid import uuid4

from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.exceptions import IrreversibleError


def fence_legacy(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    jobs = apps.get_model("basis_coach", "AIJob").objects.using(schema_editor.connection.alias)
    for pk in (
        jobs.filter(status__in=("running", "uncertain")).values_list("pk", flat=True).iterator()
    ):
        jobs.filter(pk=pk).update(attempt_id=uuid4())


def guard_reverse(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    job = apps.get_model("basis_coach", "AIJob")
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(f"LOCK TABLE {job._meta.db_table} IN ACCESS EXCLUSIVE MODE")
    if job.objects.using(schema_editor.connection.alias).filter(attempt_id__isnull=False).exists():
        raise IrreversibleError("Open attempt fence cannot be reconstructed; refusing downgrade")


class Migration(migrations.Migration):
    dependencies = [("basis_coach", "0002_frozen_pricing_reconciliation")]
    operations = [
        migrations.AddField(
            model_name="aijob",
            name="attempt_id",
            field=models.UUIDField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(fence_legacy, guard_reverse),
    ]
