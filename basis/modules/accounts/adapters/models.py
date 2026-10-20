from django.db import models


class RateWindow(models.Model):
    key = models.CharField(max_length=100, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
