from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class APIToken(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    name = models.CharField(max_length=100)
    token_prefix = models.CharField(max_length=12, unique=True)
    token_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "revoked_at"], name="api_token_owner_revoked_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.token_prefix})"
