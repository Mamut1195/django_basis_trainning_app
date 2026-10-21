from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN,
    LoginView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render

from basis.bootstrap.accounts import identity
from basis.modules.accounts.adapters.recovery import BasisSetPasswordForm
from basis.modules.accounts.adapters.recovery_actions import (
    confirm_password_reset,
    recover_password,
)
from basis.modules.accounts.adapters.web.client_address import client_address
from basis.modules.accounts.adapters.web.forms import SignupForm
from basis.modules.accounts.domain.identity import MailDeliveryUnavailable, RegistrationConflict
from basis.modules.accounts.public import (
    AccountUnavailable,
    ConsumeAttempt,
    InvalidVerification,
    RegisterAccount,
    VerifyAccount,
)


def rate_allowed(request: HttpRequest, action: str, maximum: int = 10, minutes: int = 15) -> bool:
    return identity().allow_attempt(
        ConsumeAttempt(action, client_address(request), maximum, minutes)
    )


class BasisLoginView(LoginView):
    template_name = "accounts/auth/login.html"

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if not rate_allowed(request, "login"):
            return render(
                request,
                "shared/notice.html",
                {
                    "title": "Inténtalo más tarde",
                    "text": "Se alcanzó el límite de intentos de acceso.",
                },
                status=429,
            )
        return super().post(request, *args, **kwargs)


class BasisPasswordResetView(PasswordResetView):
    template_name = "accounts/auth/password_reset_form.html"
    email_template_name = "accounts/auth/password_reset_email.html"

    def form_valid(self, form: PasswordResetForm) -> HttpResponse:
        recover_password(form, self.request)
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if not rate_allowed(request, "password-reset", maximum=5):
            return HttpResponse("Inténtalo más tarde.", status=429)
        return super().post(request, *args, **kwargs)


class BasisPasswordResetConfirmView(PasswordResetConfirmView):
    """Retain Django's token/session/CSRF flow; serialize the mutation authority."""

    form_class = BasisSetPasswordForm
    token_generator: PasswordResetTokenGenerator = default_token_generator

    def form_valid(self, form: SetPasswordForm[User]) -> HttpResponse:
        token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN)
        outcome = confirm_password_reset(
            form, token if isinstance(token, str) else None, self.token_generator
        )
        if outcome == "invalid":
            self.validlink = False
            self.request.session.pop(INTERNAL_RESET_SESSION_TOKEN, None)
            return self.render_to_response(self.get_context_data())
        if outcome == "invalid-password":
            return self.form_invalid(form)
        self.user = form.user
        self.request.session.pop(INTERNAL_RESET_SESSION_TOKEN, None)
        if self.post_reset_login:
            auth_login(self.request, self.user, self.post_reset_login_backend)
        return HttpResponseRedirect(self.get_success_url())


def signup(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and not rate_allowed(request, "signup", maximum=5):
        return HttpResponse("Inténtalo más tarde.", status=429)
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account = form.save(commit=False)
        try:
            identity().register(
                RegisterAccount(
                    email=form.cleaned_data["email"],
                    name=form.cleaned_data["name"],
                    encoded_password=account.password,
                )
            )
        except (RegistrationConflict, MailDeliveryUnavailable):
            pass
        return render(
            request,
            "shared/notice.html",
            {
                "title": "Revisa tu correo",
                "text": (
                    "Si corresponde, recibirás un enlace válido durante 24 horas. "
                    "Si no llega, puedes volver a intentar el registro, verificar tu correo "
                    "o recuperar el acceso desde el inicio de sesión."
                ),
            },
        )
    return render(
        request,
        "shared/form.html",
        {
            "title": "Empieza con BASIS",
            "subtitle": "Tu entrenamiento, tus datos y una dirección clara.",
            "form": form,
            "submit": "Crear cuenta",
        },
    )


def verify_email(request: HttpRequest, token: str) -> HttpResponse:
    try:
        identity().verify(VerifyAccount(token, confirm=request.method == "POST"))
        if request.method == "POST":
            messages.success(request, "Correo verificado. Ya puedes iniciar sesión.")
            return redirect("login")
        return render(
            request,
            "shared/confirm.html",
            {
                "title": "Verifica tu correo",
                "text": "Confirma que quieres activar tu cuenta de BASIS.",
                "submit": "Verificar correo",
            },
        )
    except AccountUnavailable as error:
        raise Http404 from error
    except InvalidVerification:
        return render(
            request,
            "shared/notice.html",
            {
                "title": "Enlace caducado o inválido",
                "text": "Solicita un nuevo correo de verificación.",
            },
            status=400,
        )


def resend_verification(request: HttpRequest) -> HttpResponse:
    from django import forms

    class EmailForm(forms.Form):
        email = forms.EmailField(label="Correo electrónico")

    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not rate_allowed(request, "resend-verification", maximum=5):
            return HttpResponse("Inténtalo más tarde.", status=429)
        try:
            identity().resend(form.cleaned_data["email"])
        except MailDeliveryUnavailable:
            pass
        return render(
            request,
            "shared/notice.html",
            {
                "title": "Revisa tu correo",
                "text": (
                    "Si existe una cuenta pendiente, recibirás un enlace de verificación. "
                    "Si no llega, inténtalo más tarde o recupera el acceso desde el inicio de sesión."
                ),
            },
        )
    return render(request, "shared/form.html", {"title": "Verificar mi correo", "form": form})
