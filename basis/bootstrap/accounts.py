"""Explicit identity composition; legacy forms only pass validated, hashed input."""

from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest

from basis.bootstrap.transactions import DjangoClock, DjangoUnitOfWork
from basis.modules.accounts.adapters.django import (
    DjangoAccounts,
    DjangoRateWindows,
    DjangoVerification,
)
from basis.modules.accounts.adapters.recovery import DjangoPasswordRecovery
from basis.modules.accounts.public import Identity, RecoverPassword, Recovery
from basis.modules.athletes.adapters.enrollment import DjangoAthleteEnrollment
from basis.modules.billing.adapters.enrollment import DjangoBillingEnrollment


def identity() -> Identity:
    return Identity(
        DjangoAccounts(),
        DjangoAthleteEnrollment(),
        DjangoBillingEnrollment(),
        DjangoVerification(),
        DjangoRateWindows(),
        DjangoUnitOfWork,
        DjangoClock(),
    )


def recover_password(form: PasswordResetForm, request: HttpRequest) -> None:
    Recovery(DjangoPasswordRecovery(form, request)).request(
        RecoverPassword(str(form.cleaned_data["email"]), request.is_secure())
    )
