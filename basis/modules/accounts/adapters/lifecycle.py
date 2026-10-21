"""Observe ordinary auth saves without changing the athlete enrollment contract."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import EmailVerification


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def disable_pending_verification(
    sender: type[AbstractUser], instance: AbstractUser, using: str, raw: bool, **kwargs: object
) -> None:
    # Saving an existing inactive account explicitly revokes its enrollment.
    # This includes disabling a pending account before its first verification.
    if not raw and not instance._state.adding and not instance.is_active:
        # Same lock order as verification: auth account first, lifecycle second.
        with transaction.atomic(using=using):
            sender._default_manager.using(using).select_for_update().get(pk=instance.pk)
            EmailVerification.objects.using(using).filter(account_id=instance.pk).update(
                state=EmailVerification.State.DISABLED
            )


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def initialize_verification(
    sender: type[AbstractUser],
    instance: AbstractUser,
    created: bool,
    using: str,
    raw: bool,
    **kwargs: object,
) -> None:
    if not raw and created:
        EmailVerification.objects.using(using).create(
            account_id=instance.pk,
            state=(
                EmailVerification.State.VERIFIED
                if instance.is_active
                else EmailVerification.State.DISABLED
            ),
        )
