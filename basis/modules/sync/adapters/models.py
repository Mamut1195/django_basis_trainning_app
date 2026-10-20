from django.conf import settings
from django.db import models


class SyncReceipt(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mutation_id = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "mutation_id"], name="sync_owner_mutation")
        ]
