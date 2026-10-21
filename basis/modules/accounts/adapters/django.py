"""Django auth, signing, mail and rate-window persistence."""

import hashlib
import logging
from smtplib import SMTPException
from typing import cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core import signing
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.urls import reverse

from basis.modules.accounts.adapters.models import EmailVerification, RateWindow
from basis.shared.identifiers import AccountId

from ..application.identity import RegisterAccount
from ..domain.identity import (
    Account,
    AccountUnavailable,
    InvalidVerification,
    MailDeliveryUnavailable,
    RateState,
    RegistrationConflict,
    VerificationClaim,
)


def account_state(row: AbstractUser) -> Account:
    return Account(AccountId(row.pk), row.email, row.first_name, row.is_active)


class DjangoAccounts:
    def lock(self, account: AccountId) -> Account:
        return account_state(get_user_model().objects.select_for_update().get(pk=account))

    def create_inactive(self, command: RegisterAccount) -> Account:
        try:
            with transaction.atomic():
                row = get_user_model().objects.create(
                    username=command.email,
                    email=command.email,
                    first_name=command.name,
                    password=command.encoded_password,
                    is_active=False,
                )
                EmailVerification.objects.filter(account_id=row.pk).update(
                    state=EmailVerification.State.PENDING
                )
        except IntegrityError as error:
            # A savepoint keeps the outer UoW usable for this classification.
            # Unexpected constraints remain visible as operational failures.
            if self.username_exists(command.email):
                raise RegistrationConflict from error
            raise
        return account_state(row)

    def by_claim(self, claim: VerificationClaim) -> Account:
        row = (
            get_user_model()
            .objects.select_for_update()
            .filter(pk=claim.account, email=claim.email)
            .first()
        )
        if row is None:
            raise AccountUnavailable
        if (
            row.is_active
            or not EmailVerification.objects.filter(
                account_id=row.pk, state=EmailVerification.State.PENDING
            ).exists()
        ):
            raise InvalidVerification
        return account_state(row)

    def pending(self, email: str) -> Account | None:
        row = (
            get_user_model()
            .objects.filter(
                email__iexact=email,
                is_active=False,
                emailverification__state=EmailVerification.State.PENDING,
            )
            .first()
        )
        return account_state(row) if row is not None else None

    def activate(self, account: AccountId) -> None:
        row = get_user_model().objects.get(pk=account)
        row.is_active = True
        row.save(update_fields=["is_active"])
        EmailVerification.objects.filter(account_id=account).update(
            state=EmailVerification.State.VERIFIED
        )

    def username_exists(self, email: str) -> bool:
        return get_user_model().objects.filter(username=email).exists()


class DjangoVerification:
    def decode(self, token: str) -> VerificationClaim:
        try:
            payload = cast(object, signing.loads(token, salt="basis-verify", max_age=86400))
        except signing.BadSignature as error:
            raise InvalidVerification from error
        if not isinstance(payload, dict):
            raise InvalidVerification
        uid, email = payload.get("uid"), payload.get("email")
        if not isinstance(uid, int) or not isinstance(email, str):
            raise InvalidVerification
        return VerificationClaim(AccountId(uid), email)

    def send(self, account: Account) -> None:
        token = signing.dumps({"uid": account.id, "email": account.email}, salt="basis-verify")
        link = settings.PUBLIC_URL + reverse("verify-email", args=[token])
        try:
            send_mail(
                "Verifica tu cuenta de BASIS",
                "Confirma tu correo para empezar:\n" + link + "\nEste enlace caduca en 24 horas.",
                settings.DEFAULT_FROM_EMAIL,
                [account.email],
            )
        except (OSError, SMTPException) as error:
            logging.getLogger("basis.accounts.mail").warning(
                "account event=verification_delivery_failed"
            )
            raise MailDeliveryUnavailable from error


class DjangoRateWindows:
    @staticmethod
    def key(action: str, address: str) -> str:
        return hashlib.sha256((action + ":" + address).encode()).hexdigest()

    def lock(self, action: str, address: str, initial: RateState) -> RateState:
        row, _ = RateWindow.objects.get_or_create(
            key=self.key(action, address), defaults={"expires_at": initial.expires_at}
        )
        row = RateWindow.objects.select_for_update().get(pk=row.pk)
        return RateState(row.count, row.expires_at)

    def save(self, action: str, address: str, state: RateState) -> None:
        row = RateWindow.objects.get(key=self.key(action, address))
        row.count, row.expires_at = state.count, state.expires_at
        row.save()
