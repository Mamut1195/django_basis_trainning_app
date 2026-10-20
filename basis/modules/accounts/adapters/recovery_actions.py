from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest

from basis.modules.accounts.adapters.recovery import DjangoPasswordRecovery
from basis.modules.accounts.public import RecoverPassword, Recovery


def recover_password(form: PasswordResetForm, request: HttpRequest) -> None:
    Recovery(DjangoPasswordRecovery(form, request)).request(
        RecoverPassword(str(form.cleaned_data["email"]), request.is_secure())
    )
