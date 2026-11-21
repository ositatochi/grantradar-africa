from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import (
    ApplicantType,
    Country,
    Currency,
    Sector,
    Theme,
    TimeStampedModel,
)
from apps.funders.models import Funder
from apps.sources.models import Source


class Opportunity(TimeStampedModel):
    class OpportunityType(models.TextChoices):
        GRANT = "grant", "Grant"
        FELLOWSHIP = "fellowship", "Fellowship"
        AWARD = "award", "Award"
        PRIZE = "prize", "Prize"
        SCHOLARSHIP = "scholarship", "Scholarship"
        TENDER = "tender", "Tender / contract"
        ACCELERATOR = "accelerator", "Accelerator"
        EXPRESSION_OF_INTEREST = "eoi", "Expression of interest"
        CALL_FOR_PROPOSALS = "cfp", "Call for proposals"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSING_SOON = "closing_soon", "Closing soon"
        CLOSED = "closed", "Closed"
        ROLLING = "rolling", "Rolling"
        UPCOMING = "upcoming", "Upcoming"
        UNVERIFIED = "unverified", "Unverified"

    title = models.CharField(max_length=300)
    funder = models.ForeignKey(
        Funder,
        on_delete=models.SET_NULL,
        related_name="opportunities",
        null=True,
        blank=True,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verified_opportunities",
        null=True,
        blank=True,
    )
    funder_name = models.CharField(max_length=200, blank=True)
    programme_name = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    description_snippet = models.TextField(blank=True)
    opportunity_type = models.CharField(max_length=24, choices=OpportunityType.choices)
    amount_min = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_max = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        related_name="opportunities",
        null=True,
        blank=True,
    )
    amount_usd = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_ngn = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    deadline_date = models.DateField(null=True, blank=True)
    deadline_time = models.TimeField(null=True, blank=True)
    deadline_timezone = models.CharField(max_length=64, default="Africa/Lagos")
    rolling = models.BooleanField(default=False)
    open_date = models.DateField(null=True, blank=True)
    eligible_countries = models.ManyToManyField(
        Country,
        blank=True,
        related_name="eligible_opportunities",
    )
    excluded_countries = models.ManyToManyField(
        Country,
        blank=True,
        related_name="excluded_opportunities",
    )
    applicant_types = models.ManyToManyField(
        ApplicantType,
        blank=True,
        related_name="opportunities",
    )
    sectors = models.ManyToManyField(Sector, blank=True, related_name="opportunities")
    themes = models.ManyToManyField(Theme, blank=True, related_name="opportunities")
    co_funding_required = models.BooleanField(default=False)
    eligibility_notes = models.TextField(blank=True)
    how_to_apply = models.TextField(blank=True)
    application_url = models.URLField(blank=True)
    official_source_url = models.URLField()
    source_name = models.CharField(max_length=200, blank=True)
    language = models.CharField(max_length=12, default="en")
    date_first_found = models.DateTimeField(null=True, blank=True)
    date_last_verified = models.DateTimeField(null=True, blank=True)
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.UNVERIFIED,
    )
    sources: models.ManyToManyField[Source, OpportunitySource] = models.ManyToManyField(
        Source,
        through="OpportunitySource",
        related_name="opportunities",
        blank=True,
    )

    class Meta:
        ordering = ["title"]
        indexes = [
            models.Index(fields=["status", "deadline_date"], name="opp_status_deadline_idx"),
            models.Index(fields=["date_last_verified"], name="opportunity_verified_idx"),
            models.Index(fields=["funder", "status"], name="opportunity_funder_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(amount_min__isnull=True)
                    | Q(amount_max__isnull=True)
                    | Q(amount_min__lte=F("amount_max"))
                ),
                name="opportunity_amount_range_valid",
            ),
            models.CheckConstraint(
                condition=Q(confidence_score__gte=0) & Q(confidence_score__lte=1),
                name="opportunity_confidence_between_0_1",
            ),
            models.CheckConstraint(
                condition=Q(status="unverified") | Q(date_last_verified__isnull=False),
                name="verified_opportunity_has_date",
            ),
            models.CheckConstraint(
                condition=(
                    Q(date_first_found__isnull=True)
                    | Q(date_last_verified__isnull=True)
                    | Q(date_last_verified__gte=F("date_first_found"))
                ),
                name="opportunity_verification_ordered",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.summary and len(self.summary.split()) > 120:
            raise ValidationError({"summary": "Summary must be 120 words or fewer."})
        try:
            ZoneInfo(self.deadline_timezone)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ValidationError({"deadline_timezone": "Enter a valid IANA timezone."}) from error
        if self.deadline_date and self.open_date and self.deadline_date < self.open_date:
            raise ValidationError({"deadline_date": "Deadline cannot be before the opening date."})

    def __str__(self) -> str:
        return self.title


class OpportunitySource(models.Model):
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="source_links",
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="opportunity_links",
    )
    source_url = models.URLField()
    canonical_url = models.URLField()
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["source__name", "canonical_url"]
        indexes = [
            models.Index(fields=["source", "canonical_url"], name="opp_source_url_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["opportunity", "canonical_url"],
                name="opportunity_canonical_source_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.opportunity} — {self.source}"


class ErrorReport(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWING = "reviewing", "Reviewing"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.SET_NULL,
        related_name="error_reports",
        null=True,
        blank=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="error_reports",
        null=True,
        blank=True,
    )
    source_url = models.URLField()
    description = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="error_status_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Report for {self.source_url}"
