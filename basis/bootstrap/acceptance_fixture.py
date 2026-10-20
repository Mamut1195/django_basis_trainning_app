"""Disposable browser acceptance data; only invoked by the isolated launcher."""

import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User as Account
from django.utils import timezone

from basis.modules.athletes.adapters.models import AthleteSettings, User
from basis.modules.billing.adapters.models import BillingAccount


def prepare() -> None:
    expected = Path(os.environ["BASIS_ACCEPTANCE_DATABASE"]).resolve()
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        raise RuntimeError("Browser acceptance requires its own SQLite database")
    if Path(settings.DATABASES["default"]["NAME"]).resolve() != expected:
        raise RuntimeError("Browser fixture database identity mismatch")
    if not expected.is_relative_to((settings.BASE_DIR / ".cache").resolve()):
        raise RuntimeError("Browser fixture must stay in the owned cache")
    password = os.environ["BASIS_E2E_PASSWORD"]
    now = timezone.now()
    for email, name in (
        ("owner@browser.test", "Browser Owner"),
        ("other@browser.test", "Browser Other"),
    ):
        account = Account.objects.create_user(username=email, email=email, password=password)
        User.objects.create(
            account=account,
            nombre=name,
            email=email,
            fecha_inicio=now.date(),
            email_verified=True,
            edad=30,
        )
        AthleteSettings.objects.create(owner=account)
        BillingAccount.objects.create(
            owner=account,
            status="active",
            period_start=now - timedelta(days=1),
            period_end=now + timedelta(days=30),
        )
