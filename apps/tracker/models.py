from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.opportunities.models import Opportunity
from apps.teams.models import Team


class Bookmark(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "opportunity"],
                name="bookmark_owner_opportunity_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.owner}: {self.opportunity}"


class PipelineItem(TimeStampedModel):
    class Status(models.TextChoices):
        INTERESTED = "interested", "Interested"
        PREPARING = "preparing", "Preparing"
        SUBMITTED = "submitted", "Submitted"
        AWARDED = "awarded", "Awarded"
        REJECTED = "rejected", "Rejected"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pipeline_items",
    )
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="pipeline_items",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        related_name="pipeline_items",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INTERESTED)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_pipeline_items",
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "opportunity"],
                name="pipeline_owner_opportunity_unique",
            )
        ]
        indexes = [
            models.Index(fields=["owner", "status"], name="pipeline_owner_status_idx"),
            models.Index(fields=["team", "status"], name="pipeline_team_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.opportunity} — {self.status}"


class Note(TimeStampedModel):
    pipeline_item = models.ForeignKey(
        PipelineItem,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pipeline_notes",
    )
    content = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Note by {self.author} on {self.pipeline_item}"


class DeadlineReminder(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    pipeline_item = models.ForeignKey(
        PipelineItem,
        on_delete=models.CASCADE,
        related_name="deadline_reminders",
    )
    deadline_date = models.DateField()
    days_before = models.PositiveSmallIntegerField(
        choices=[(14, "14 days"), (7, "7 days"), (3, "3 days"), (1, "1 day")]
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.QUEUED)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["deadline_date", "days_before"]
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_item", "deadline_date", "days_before"],
                name="deadline_reminder_item_date_days_unique",
            ),
            models.CheckConstraint(
                condition=Q(days_before__in=[14, 7, 3, 1]),
                name="deadline_reminder_days_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pipeline_item} — {self.days_before} days before"
