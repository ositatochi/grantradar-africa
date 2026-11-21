from django.conf import settings
from django.db import models

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
