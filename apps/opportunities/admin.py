from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin as DjangoModelAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.core.admin_types import UnfoldModelAdmin as ModelAdmin
from apps.core.admin_types import UnfoldTabularInline as TabularInline
from apps.opportunities.models import ErrorReport, Opportunity, OpportunitySource
from apps.pipeline.services import REVIEW_CONFIDENCE_THRESHOLD, verify_opportunity


class ConfidenceReviewFilter(admin.SimpleListFilter):
    title = _("review confidence")
    parameter_name = "review_confidence"

    def lookups(
        self,
        request: HttpRequest,
        model_admin: DjangoModelAdmin[Any],
    ) -> tuple[tuple[str, str], ...]:
        return (("low", str(_("Low confidence"))),)

    def queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet[Opportunity],
    ) -> QuerySet[Opportunity]:
        if self.value() == "low":
            return queryset.filter(confidence_score__lt=REVIEW_CONFIDENCE_THRESHOLD)
        return queryset


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
        "date_first_found",
        "date_last_verified",
        "confidence_score",
    )
    list_filter = (
        "status",
        ConfidenceReviewFilter,
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
    readonly_fields = ("created_at", "updated_at", "date_first_found")
    inlines = (OpportunitySourceInline,)
    date_hierarchy = "date_first_found"
    ordering = ("confidence_score", "-date_first_found")
    actions = ("verify_selected_opportunities",)

    @admin.action(description=_("Verify selected opportunities"))
    def verify_selected_opportunities(
        self,
        request: HttpRequest,
        queryset: QuerySet[Opportunity],
    ) -> None:
        if not isinstance(request.user, User):
            raise PermissionDenied
        verified = 0
        for opportunity in queryset.filter(status=Opportunity.Status.UNVERIFIED).iterator():
            verify_opportunity(opportunity, request.user)
            verified += 1
        self.message_user(
            request,
            _("Verified %(count)s opportunities.") % {"count": verified},
            level=messages.SUCCESS,
        )


@admin.register(ErrorReport)
class ErrorReportAdmin(ModelAdmin):
    list_display = ("source_url", "opportunity", "status", "submitted_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("source_url", "description", "opportunity__title")
    readonly_fields = ("created_at", "updated_at")
