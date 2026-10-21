from django.conf import settings
from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
import django.db.models.deletion


def initialize_lifecycle(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Verification = apps.get_model("basis_accounts", "EmailVerification")
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    Account = apps.get_model(app_label, model_name)
    alias = schema_editor.connection.alias
    # Historical inactive rows do not tell us whether an operator disabled them.
    # Fail closed rather than silently restoring their ability to self-activate.
    for account in Account.objects.using(alias).all().iterator():
        Verification.objects.using(alias).get_or_create(
            account_id=account.pk,
            defaults={"state": "verified" if account.is_active else "disabled"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("basis_accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="EmailVerification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state", models.CharField(choices=[("pending", "Pending"), ("verified", "Verified"), ("disabled", "Disabled")], max_length=10)),
                ("account", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(initialize_lifecycle, migrations.RunPython.noop),
    ]
