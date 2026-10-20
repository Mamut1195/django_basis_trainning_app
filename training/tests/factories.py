from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from basis.modules.athletes.adapters.models import AthleteSettings
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.training.adapters.models import Block, Goal, Session


def account(name="athlete", status="active"):
    user = get_user_model().objects.create_user(
        username=name + "@example.test",
        email=name + "@example.test",
        password="Example-password-824!",
    )
    Athlete.objects.create(
        account=user,
        nombre=name,
        email=user.email,
        fecha_inicio=timezone.localdate(),
        email_verified=True,
        edad=25,
    )
    AthleteSettings.objects.create(owner=user, availability=[1, 3, 5])
    BillingAccount.objects.create(
        owner=user,
        polar_customer_id="customer-" + name,
        status=status,
        period_start=timezone.now() - timedelta(days=1),
        period_end=timezone.now() + timedelta(days=29),
    )
    return user


def exercise():
    classification, _ = Classification.objects.get_or_create(nombre="Fuerza")
    return Exercise.objects.create(nombre="Sentadilla", classification=classification)


def session(owner, sport="running", **kwargs):
    item = Session.objects.create(owner=owner, title="Entrenamiento", **kwargs)
    Block.objects.create(session=item, sport=sport, title="Bloque")
    return item


def proposal(owner):
    goal = Goal.objects.create(owner=owner, title="Constancia", sport="running")
    start = timezone.localdate().isoformat()
    end = (timezone.localdate() + timedelta(days=6)).isoformat()
    return {
        "title": "Semana inicial",
        "goal_id": goal.pk,
        "start_date": start,
        "end_date": end,
        "cycles": [
            {
                "key": "ma",
                "parent": None,
                "kind": "macro",
                "title": "Base",
                "start_date": start,
                "end_date": end,
            },
            {
                "key": "me",
                "parent": "ma",
                "kind": "meso",
                "title": "Base",
                "start_date": start,
                "end_date": end,
            },
            {
                "key": "mi",
                "parent": "me",
                "kind": "micro",
                "title": "Semana",
                "start_date": start,
                "end_date": end,
            },
        ],
        "sessions": [
            {
                "title": "Rodaje",
                "date": start,
                "cycle_key": "mi",
                "blocks": [
                    {"sport": "running", "title": "Suave", "target": {"duration_seconds": 1800}}
                ],
            }
        ],
    }
