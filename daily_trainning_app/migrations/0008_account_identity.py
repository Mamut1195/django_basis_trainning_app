import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_ids(apps, schema_editor):
    Profile = apps.get_model("daily_trainning_app", "User")
    for pk in Profile.objects.using(schema_editor.connection.alias).values_list("pk", flat=True).iterator():
        Profile.objects.using(schema_editor.connection.alias).filter(pk=pk).update(public_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("daily_trainning_app", "0007_user_ciudad_user_descripcion_user_edad_and_more"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="user", name="account", field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="athlete", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="user", name="public_id", field=models.UUIDField(null=True, unique=True, editable=False)),
        migrations.RunPython(assign_ids, migrations.RunPython.noop),
        migrations.AlterField(model_name="user", name="public_id", field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
        migrations.AddField(model_name="user", name="email_verified", field=models.BooleanField(default=False)),
    ]
