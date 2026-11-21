from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import Country, Sector, TimeStampedModel


class Source(TimeStampedModel):
    class SourceType(models.TextChoices):
        API = "api", "API"
        RSS = "rss", "RSS"
        HTML_LIST = "html_list", "HTML list"
        HTML_DETAIL = "html_detail", "HTML detail"
        SITEMAP = "sitemap", "Sitemap"
        NEWSLETTER_EMAIL = "newsletter_email", "Newsletter email"

    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    url = models.URLField(unique=True)
    crawl_frequency_hours = models.PositiveSmallIntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(8760)],
    )
    adapter_class = models.CharField(max_length=255, blank=True)
    selectors = models.JSONField(default=dict, blank=True)
    countries = models.ManyToManyField(Country, blank=True, related_name="sources")
    sectors = models.ManyToManyField(Sector, blank=True, related_name="sources")
    reliability_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=0.500,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    enabled = models.BooleanField(default=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_record_count = models.PositiveIntegerField(default=0)
    failure_streak = models.PositiveSmallIntegerField(default=0)
    average_yield = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["enabled", "source_type"], name="source_enabled_type_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(reliability_score__gte=0) & Q(reliability_score__lte=1),
                name="source_reliability_between_0_1",
            ),
            models.CheckConstraint(
                condition=Q(crawl_frequency_hours__gte=1),
                name="source_crawl_interval_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class SearchQuery(TimeStampedModel):
    name = models.CharField(max_length=160, unique=True)
    query_template = models.CharField(max_length=500)
    sector = models.ForeignKey(
        Sector,
        on_delete=models.SET_NULL,
        related_name="discovery_queries",
        null=True,
        blank=True,
    )
    countries = models.ManyToManyField(Country, blank=True, related_name="discovery_queries")
    opportunity_type = models.CharField(max_length=32, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["enabled", "year"], name="search_query_active_year_idx")]

    def __str__(self) -> str:
        return self.name


class CandidateSource(TimeStampedModel):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    url = models.URLField(unique=True)
    name = models.CharField(max_length=200, blank=True)
    discovery_query = models.ForeignKey(
        SearchQuery,
        on_delete=models.SET_NULL,
        related_name="candidate_sources",
        null=True,
        blank=True,
    )
    review_status = models.CharField(
        max_length=12,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewer_notes = models.TextField(blank=True)
    promoted_source = models.OneToOneField(
        Source,
        on_delete=models.SET_NULL,
        related_name="candidate_record",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["review_status", "created_at"], name="candidate_review_created_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.name or self.url
