import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("basis_training", "0002_planning_version_history")]
    operations = [
        migrations.AddField(model_name=name, name="source", field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="execution_copies", to="basis_training." + name))
        for name in ("block", "strengthset", "interval")
    ] + [
        migrations.AddField(model_name="strengthset", name="actual_exercise", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="performed_sets", to="basis_catalog.exercise")),
        migrations.AddField(model_name="strengthset", name="actual_load_type", field=models.CharField(blank=True, choices=[("external", "Carga externa"), ("bodyweight", "Peso corporal"), ("assisted", "Asistida")], max_length=12, null=True)),
        migrations.AddField(model_name="strengthset", name="actual_kind", field=models.CharField(blank=True, choices=[("warmup", "Calentamiento"), ("work", "Trabajo"), ("failed", "Fallida")], max_length=12, null=True)),
        migrations.AddField(model_name="strengthset", name="actual_tempo", field=models.CharField(blank=True, max_length=30, null=True)),
        migrations.AddField(model_name="strengthset", name="actual_range_of_motion", field=models.CharField(blank=True, max_length=80, null=True)),
        migrations.AddField(model_name="strengthset", name="actual_side", field=models.CharField(blank=True, choices=[("both", "Bilateral"), ("left", "Izquierda"), ("right", "Derecha")], max_length=10, null=True)),
        migrations.AddField(model_name="strengthset", name="actual_group", field=models.CharField(blank=True, max_length=80, null=True)),
        migrations.AddField(model_name="strengthset", name="adaptation_reason", field=models.CharField(blank=True, max_length=1000)),
    ]
