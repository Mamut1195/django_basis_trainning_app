"""Presentation of the sourced MAM-815 session context."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from basis.modules.training.adapters.models import Block, Session, TrekStage, TrekTrip
from tests.regression.factories import account


class ProgressContextUXTests(TestCase):
    def test_context_sources_missing_zero_escaping_and_account_isolation(self) -> None:
        owner = account("context-ux-owner")
        other = account("context-ux-other")
        self.client.force_login(owner)
        first = Session.objects.create(
            owner=owner,
            title="Primera",
            date=date(2026, 10, 12),
            status="completed",
            duration_seconds=None,
            reported_rpe=None,
        )
        second = Session.objects.create(
            owner=owner,
            title="Segunda",
            date=date(2026, 10, 13),
            status="completed",
            duration_seconds=0,
            reported_rpe=Decimal(0),
        )
        Block.objects.create(session=first, title="Run", sport="running")
        Block.objects.create(session=second, title="Hike", sport="hiking")
        trip = TrekTrip.objects.create(owner=owner, title="Viaje propio")
        TrekStage.objects.create(
            trip=trip,
            session=second,
            order=1,
            overnight_altitude_m=Decimal(0),
            recovery_notes='<script>alert("x")</script> nota declarada',
        )
        foreign = Session.objects.create(
            owner=other,
            title="Foreign context private",
            date=date(2026, 10, 13),
            status="completed",
        )
        self.client.force_login(owner)
        response = self.client.get(
            reverse("progress"),
            {
                "period": "range",
                "start": "2026-10-12",
                "end": "2026-10-13",
            },
        )
        self.assertContains(response, reverse("session-detail", args=[first.pk]))
        self.assertContains(response, reverse("session-detail", args=[second.pk]))
        self.assertContains(response, reverse("trip-detail", args=[trip.pk]))
        self.assertContains(response, "&lt;script&gt;alert")
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertNotContains(response, "Foreign context private")
        self.assertNotContains(response, str(foreign.pk))
        self.assertContains(response, "sin inferir descanso")
        self.assertContains(response, "Diferencia de fechas (días)")
        self.assertContains(response, "Altitud de pernocta: 0,00 m")
        self.assertContains(response, "<dt>Duración (s)</dt> <dd>0</dd>", html=True)
        self.assertContains(response, "<dt>Duración (s)</dt> <dd>Sin dato</dd>", html=True)
        self.assertContains(response, "<dt>Carga interna (UA)</dt> <dd>0,00</dd>", html=True)
        self.assertContains(response, "<dt>Carga interna (UA)</dt> <dd>Sin dato</dd>", html=True)
        self.assertContains(response, "Tiempo transcurrido")
        self.assertContains(response, "Días consecutivos observados")
        self.client.force_login(other)
        other_report = self.client.get(reverse("progress"))
        self.assertNotContains(other_report, "nota declarada")
        self.assertNotContains(other_report, str(second.pk))
        self.assertEqual(
            self.client.get(reverse("session-detail", args=[second.pk])).status_code, 404
        )
        self.assertEqual(self.client.get(reverse("trip-detail", args=[trip.pk])).status_code, 404)
