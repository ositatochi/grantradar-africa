from django.db import models
from django.db.models import Q

from apps.sources.models import Source


class SourceRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    pages_crawled = models.PositiveIntegerField(default=0)
    records_found = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        indexes = [models.Index(fields=["source", "started_at"], name="source_run_started_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(completed_at__isnull=True)
                    | Q(started_at__isnull=True)
                    | Q(completed_at__gte=models.F("started_at"))
                ),
                name="source_run_times_ordered",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source} — {self.status}"


class RawDocument(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        IGNORED = "ignored", "Ignored"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="documents")
    source_run = models.ForeignKey(
        SourceRun,
        on_delete=models.SET_NULL,
        related_name="documents",
        null=True,
        blank=True,
    )
    url = models.URLField()
    canonical_url = models.URLField()
    content_type = models.CharField(max_length=120, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    content_hash = models.CharField(max_length=64)
    compressed_content = models.BinaryField()
    etag = models.CharField(max_length=255, blank=True)
    last_modified = models.CharField(max_length=255, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    processing_status = models.CharField(
        max_length=12,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [
            models.Index(fields=["source", "canonical_url"], name="raw_doc_source_url_idx"),
            models.Index(fields=["content_hash"], name="raw_doc_content_hash_idx"),
            models.Index(
                fields=["processing_status", "fetched_at"],
                name="raw_doc_processing_fetched_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "canonical_url", "content_hash"],
                name="raw_doc_source_url_hash_unique",
            )
        ]

    def __str__(self) -> str:
        return self.canonical_url
