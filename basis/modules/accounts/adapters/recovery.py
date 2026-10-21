"""Preserve Django's PasswordResetForm, request/site context and default token generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import router, transaction
from django.http import HttpRequest

from ..application.recovery import ConfirmPasswordReset, RecoverPassword, ResetOutcome
from .models import EmailVerification

if TYPE_CHECKING:
    TypedSetPasswordForm = SetPasswordForm[User]
else:
    TypedSetPasswordForm = SetPasswordForm


class DjangoPasswordRecovery:
    def __init__(self, form: PasswordResetForm, request: HttpRequest) -> None:
        self.form, self.request = form, request

    def send(self, command: RecoverPassword) -> None:
        self.form.save(
            use_https=command.secure,
            request=self.request,
            email_template_name="accounts/auth/password_reset_email.html",
            subject_template_name="accounts/auth/password_reset_subject.txt",
        )


class BasisSetPasswordForm(TypedSetPasswordForm):
    """Only the password field is persisted; authorization belongs to the authority."""

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        if commit:
            user.save(using=user._state.db, update_fields=["password"])
        return user


class DjangoResetAuthority:
    def __init__(self, form: SetPasswordForm[User], generator: PasswordResetTokenGenerator) -> None:
        self.form, self.generator = form, generator

    def confirm(self, command: ConfirmPasswordReset) -> ResetOutcome:
        alias = self.form.user._state.db or router.db_for_write(
            type(self.form.user), instance=self.form.user
        )
        with transaction.atomic(using=alias):
            user = (
                get_user_model()
                .objects.using(alias)
                .select_for_update()
                .filter(pk=command.account)
                .first()
            )
            if (
                user is None
                or not user.is_active
                or not user.has_usable_password()
                or not EmailVerification.objects.using(alias)
                .filter(account_id=user.pk, state=EmailVerification.State.VERIFIED)
                .exists()
                or not self.generator.check_token(user, command.token)
            ):
                return "invalid"
            self.form.user = user
            self.form.validate_password_for_user(user, "new_password2")
            if self.form.errors:
                return "invalid-password"
            self.form.save()
            return "updated"
