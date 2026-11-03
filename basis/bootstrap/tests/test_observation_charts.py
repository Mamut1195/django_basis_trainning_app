from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from basis.bootstrap.tests.test_execution import account
from basis.modules.athletes.adapters.models import Measurement, Wellness


class ObservationChartTests(TestCase):
    def setUp(self) -> None:
        self.user = account("chart-owner")
        self.other = account("chart-other")
        self.client.force_login(self.user)
        self.day = timezone.localdate()

    def test_weight_chart_uses_only_dated_own_rows_with_decimal_html_values(self) -> None:
        measured = Measurement.objects.create(
            owner=self.user, date=self.day, weight_kg=Decimal("72.35")
        )
        Measurement.objects.create(
            owner=self.user, date=None, origin="legacy_profile", weight_kg=Decimal("0")
        )
        Measurement.objects.create(owner=self.other, date=self.day, weight_kg=Decimal("99.00"))
        response = self.client.get(reverse("measurement-history"))
        self.assertEqual(list(response.context["chart_rows"]), [measured])
        self.assertContains(response, 'value="72.35"')
        self.assertContains(response, f'href="#measurement-{measured.pk}"')
        self.assertNotContains(response, 'value="99.00"')
        self.assertNotContains(response, 'value="0.00"')
        self.assertContains(response, "Fecha de medici\u00f3n desconocida")

    def test_wellness_chart_shows_missing_without_a_meter_and_links_source(self) -> None:
        row = Wellness.objects.create(owner=self.user, date=self.day, fatigue=3)
        Wellness.objects.create(owner=self.other, date=self.day, fatigue=5)
        response = self.client.get(reverse("wellness-history"))
        self.assertContains(response, f'href="#wellness-{row.pk}"')
        self.assertContains(response, 'aria-label="Fatiga 3 de 5"')
        self.assertNotContains(response, 'aria-label="Disposici\u00f3n')
        self.assertContains(response, "Sin dato")
        self.assertNotContains(response, 'aria-label="Fatiga 5 de 5"')
        invalid = self.client.get(reverse("wellness-history"), {"start": "bad"})
        self.assertNotContains(invalid, "Evoluci\u00f3n de bienestar", status_code=400)
        empty = self.client.get(
            reverse("wellness-history"),
            {
                "start": (self.day - timedelta(days=3)).isoformat(),
                "end": (self.day - timedelta(days=1)).isoformat(),
            },
        )
        self.assertContains(empty, "Sin registros para este rango")
