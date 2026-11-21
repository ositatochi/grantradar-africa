from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class SavedSearch(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    name = models.CharField(max_length=160)
    query = models.CharField(max_length=300, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="saved_search_owner_name_unique",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Alert(TimeStampedModel):
    class Frequency(models.TextChoices):
        INSTANT = "instant", "Instant"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        TELEGRAM = "telegram", "Telegram"
        WHATSAPP = "whatsapp", "WhatsApp"

    saved_search = models.ForeignKey(
        SavedSearch,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    frequency = models.CharField(max_length=8, choices=Frequency.choices, default=Frequency.DAILY)
    channel = models.CharField(max_length=12, choices=Channel.choices, default=Channel.EMAIL)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    next_delivery_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["next_delivery_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["saved_search", "channel"],
                name="alert_saved_search_channel_unique",
            ),
            models.CheckConstraint(
                condition=Q(is_active=False) | Q(consent_given_at__isnull=False),
                name="alert_active_requires_consent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.saved_search} ({self.channel})"


class AlertDelivery(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.QUEUED)
    scheduled_at = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    opportunity_ids = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-scheduled_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"], name="alert_delivery_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.alert} — {self.status}"
