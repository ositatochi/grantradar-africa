from typing import Any

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from apps.core.models import TimeStampedModel
from apps.opportunities.models import Opportunity


class Team(TimeStampedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_teams",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class TeamMember(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EDITOR = "editor", "Editor"
        MEMBER = "member", "Member"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(max_length=8, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["team__name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                name="team_member_team_user_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.team} ({self.role})"


class Comment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending moderation"
        VISIBLE = "visible", "Visible"
        HIDDEN = "hidden", "Hidden"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="comments",
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="comments",
        null=True,
        blank=True,
    )
    body = models.TextField(validators=[MinLengthValidator(1)])
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(team__isnull=False) | Q(opportunity__isnull=False),
                name="comment_has_target",
            )
        ]

    def __str__(self) -> str:
        return f"Comment by {self.author}"
