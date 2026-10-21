"""Add provenance without guessing links, reasons or dates for legacy records."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("basis_training", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # All legacy origins remain NULL; uniqueness only constrains known copies.
        migrations.AddField(
            model_name="trainingplan",
            name="change_kind",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="trainingplan", name="change_reason", field=models.TextField(blank=True)
        ),
        migrations.AddField(
            model_name="trainingplan",
            name="changed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="planning_changes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="trainingplan",
            name="effective_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trainingplan",
            name="restored_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="restorations",
                to="basis_training.trainingplan",
            ),
        ),
        migrations.AddField(
            model_name="plannedsession",
            name="origin",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="copies",
                to="basis_training.plannedsession",
            ),
        ),
        migrations.AddField(
            model_name="plannedsession",
            name="supersedes",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="replacements",
                to="basis_training.plannedsession",
            ),
        ),
        migrations.AddField(
            model_name="plannedsession",
            name="status",
            field=models.CharField(
                choices=[
                    ("scheduled", "Programada"),
                    ("skipped", "Omitida"),
                    ("cancelled", "Cancelada"),
                ],
                default="scheduled",
                max_length=12,
            ),
        ),
        migrations.AddConstraint(
            model_name="plannedsession",
            constraint=models.UniqueConstraint(
                fields=("plan", "origin"), name="scheduled_plan_origin"
            ),
        ),
    ]
