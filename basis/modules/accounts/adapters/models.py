from django.conf import settings
from django.db import models


class RateWindow(models.Model):
    key = models.CharField(max_length=100, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()


class EmailVerification(models.Model):
    """Only an explicitly pending enrollment can activate an inactive account."""

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        DISABLED = "disabled", "Disabled"

    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    state = models.CharField(max_length=10, choices=State.choices)
