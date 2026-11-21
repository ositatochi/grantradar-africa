from django.contrib import admin

from apps.core.admin_types import UnfoldModelAdmin as ModelAdmin
from apps.core.admin_types import UnfoldTabularInline as TabularInline
from apps.opportunities.models import ErrorReport, Opportunity, OpportunitySource


class OpportunitySourceInline(TabularInline):
    model = OpportunitySource
    extra = 0
    readonly_fields = ("first_seen_at",)


@admin.register(Opportunity)
class OpportunityAdmin(ModelAdmin):
    list_display = (
        "title",
        "funder_name",
        "opportunity_type",
        "status",
        "deadline_date",
        "date_last_verified",
        "confidence_score",
    )
    list_filter = (
        "status",
        "opportunity_type",
        "rolling",
        "co_funding_required",
        "sectors",
        "applicant_types",
    )
    search_fields = ("title", "funder_name", "programme_name", "official_source_url")
    filter_horizontal = (
        "eligible_countries",
        "excluded_countries",
        "applicant_types",
        "sectors",
        "themes",
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = (OpportunitySourceInline,)
    date_hierarchy = "date_last_verified"


@admin.register(ErrorReport)
class ErrorReportAdmin(ModelAdmin):
    list_display = ("source_url", "opportunity", "status", "submitted_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("source_url", "description", "opportunity__title")
    readonly_fields = ("created_at", "updated_at")
