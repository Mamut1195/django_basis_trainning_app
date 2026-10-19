"""Preserve Django's PasswordResetForm, request/site context and default token generator."""

from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest

from ..application.recovery import RecoverPassword


class DjangoPasswordRecovery:
    def __init__(self, form: PasswordResetForm, request: HttpRequest) -> None:
        self.form, self.request = form, request

    def send(self, command: RecoverPassword) -> None:
        self.form.save(
            use_https=command.secure,
            request=self.request,
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        )
