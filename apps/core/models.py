from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Country(models.Model):
    alpha_2 = models.CharField(max_length=2, unique=True)
    alpha_3 = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=120, unique=True)
    region = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self) -> str:
        return self.name


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    numeric_code = models.CharField(max_length=3, blank=True)
    symbol = models.CharField(max_length=8, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "currencies"

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class SustainableDevelopmentGoal(models.Model):
    number = models.PositiveSmallIntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(17)],
    )
    title = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Sustainable Development Goal"
        verbose_name_plural = "Sustainable Development Goals"
        constraints = [
            models.CheckConstraint(
                condition=Q(number__gte=1) & Q(number__lte=17),
                name="sdg_number_between_1_17",
            )
        ]

    def __str__(self) -> str:
        return f"SDG {self.number}: {self.title}"


class Sector(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    sdg_goal = models.ForeignKey(
        SustainableDevelopmentGoal,
        on_delete=models.SET_NULL,
        related_name="sectors",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["sdg_goal", "parent"], name="sector_sdg_parent_idx")]

    def __str__(self) -> str:
        return self.name


class Theme(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ApplicantType(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Applicant type"
        verbose_name_plural = "Applicant types"

    def __str__(self) -> str:
        return self.name


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id"], name="audit_object_idx")]
        constraints = [
            models.CheckConstraint(
                condition=~Q(action=""),
                name="audit_action_not_empty",
            )
        ]

    def __str__(self) -> str:
        return f"{self.action}: {self.object_type} {self.object_id}"
