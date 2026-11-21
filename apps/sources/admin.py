from django.contrib import admin

from apps.core.admin_types import UnfoldModelAdmin as ModelAdmin
from apps.sources.models import CandidateSource, SearchQuery, Source


@admin.register(Source)
class SourceAdmin(ModelAdmin):
    list_display = (
        "name",
        "source_type",
        "url",
        "enabled",
        "reliability_score",
        "last_success_at",
        "last_record_count",
        "failure_streak",
    )
    list_filter = ("enabled", "source_type", "countries", "sectors")
    search_fields = ("name", "url", "adapter_class")
    filter_horizontal = ("countries", "sectors")
    readonly_fields = (
        "last_success_at",
        "last_record_count",
        "failure_streak",
        "average_yield",
        "created_at",
        "updated_at",
    )
    ordering = ("name",)


@admin.register(SearchQuery)
class SearchQueryAdmin(ModelAdmin):
    list_display = ("name", "sector", "opportunity_type", "year", "enabled", "last_run_at")
    list_filter = ("enabled", "year", "sector")
    search_fields = ("name", "query_template")
    filter_horizontal = ("countries",)


@admin.register(CandidateSource)
class CandidateSourceAdmin(ModelAdmin):
    list_display = ("name", "url", "review_status", "discovery_query", "created_at")
    list_filter = ("review_status", "created_at")
    search_fields = ("name", "url", "reviewer_notes")
    readonly_fields = ("created_at", "updated_at")
