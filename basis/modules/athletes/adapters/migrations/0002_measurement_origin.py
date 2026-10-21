from decimal import Decimal

import django.core.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("basis_athletes", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="measurement",
            name="origin",
            field=models.CharField(
                choices=[("measured", "Medición"), ("legacy_profile", "Perfil sin fecha")],
                default="measured", max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="measurement", name="date",
            field=models.DateField(blank=True, default=django.utils.timezone.localdate, null=True),
        ),
        migrations.AlterField(
            model_name="measurement", name="weight_kg",
            field=models.DecimalField(
                decimal_places=2, max_digits=6,
                validators=[django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("999.99"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="measurement",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(origin="measured", date__isnull=False, weight_kg__gte=Decimal("0.01"), weight_kg__lte=500)
                    | models.Q(origin="legacy_profile", date__isnull=True, weight_kg__gte=0, weight_kg__lte=Decimal("999.99"))
                ), name="measurement_origin_date_weight",
            ),
        ),
    ]
