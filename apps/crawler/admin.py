from django.contrib import admin
from django.http import HttpRequest

from apps.core.admin_types import UnfoldModelAdmin as ModelAdmin
from apps.crawler.models import RawDocument, SourceRun


@admin.register(SourceRun)
class SourceRunAdmin(ModelAdmin):
    list_display = (
        "source",
        "status",
        "started_at",
        "completed_at",
        "pages_crawled",
        "records_found",
    )
    list_filter = ("status", "source")
    search_fields = ("source__name", "error_summary")
    readonly_fields = (
        "source",
        "status",
        "started_at",
        "completed_at",
        "pages_crawled",
        "records_found",
        "error_summary",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: SourceRun | None = None) -> bool:
        return False


@admin.register(RawDocument)
class RawDocumentAdmin(ModelAdmin):
    list_display = ("source", "canonical_url", "status_code", "content_hash", "fetched_at")
    list_filter = ("source", "status_code")
    search_fields = ("url", "canonical_url", "content_hash")
    readonly_fields = (
        "source",
        "source_run",
        "url",
        "canonical_url",
        "content_type",
        "status_code",
        "content_hash",
        "etag",
        "last_modified",
        "fetched_at",
    )
    exclude = ("compressed_content",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: RawDocument | None = None) -> bool:
        return False
