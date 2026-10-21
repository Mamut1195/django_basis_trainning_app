from __future__ import annotations

from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.http import HttpRequest

from basis.modules.accounts.adapters.recovery import DjangoPasswordRecovery, DjangoResetAuthority
from basis.modules.accounts.application.recovery import (
    ConfirmPasswordReset,
    ResetConfirmation,
    ResetOutcome,
)
from basis.modules.accounts.public import RecoverPassword, Recovery
from basis.shared.identifiers import AccountId


def recover_password(form: PasswordResetForm, request: HttpRequest) -> None:
    Recovery(DjangoPasswordRecovery(form, request)).request(
        RecoverPassword(str(form.cleaned_data["email"]), request.is_secure())
    )


def confirm_password_reset(
    form: SetPasswordForm[User], token: str | None, generator: PasswordResetTokenGenerator
) -> ResetOutcome:
    return ResetConfirmation(DjangoResetAuthority(form, generator)).confirm(
        ConfirmPasswordReset(AccountId(form.user.pk), token)
    )
