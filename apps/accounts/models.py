from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import ApplicantType, Country, Sector


class User(AbstractUser):
    email = models.EmailField(unique=True)
    organization_name = models.CharField(max_length=200, blank=True)
    organization_type = models.ForeignKey(
        ApplicantType,
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True,
    )
    profile_countries = models.ManyToManyField(
        Country,
        blank=True,
        related_name="interested_users",
    )
    profile_sectors = models.ManyToManyField(
        Sector,
        blank=True,
        related_name="interested_users",
    )
    budget_min_usd = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    budget_max_usd = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    deadline_reminders_enabled = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(budget_min_usd__isnull=True)
                    | Q(budget_max_usd__isnull=True)
                    | Q(budget_min_usd__lte=F("budget_max_usd"))
                ),
                name="user_budget_range_valid",
            )
        ]
