from django.contrib import admin
from django.http import HttpRequest

from apps.core.admin_types import UnfoldModelAdmin as ModelAdmin
from apps.core.models import (
    ApplicantType,
    AuditLog,
    Country,
    Currency,
    Sector,
    SustainableDevelopmentGoal,
    Theme,
)


@admin.register(Country)
class CountryAdmin(ModelAdmin):
    list_display = ("name", "alpha_2", "alpha_3", "region")
    list_filter = ("region",)
    search_fields = ("name", "alpha_2", "alpha_3")
    ordering = ("name",)


@admin.register(Currency)
class CurrencyAdmin(ModelAdmin):
    list_display = ("code", "name", "numeric_code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(SustainableDevelopmentGoal)
class SustainableDevelopmentGoalAdmin(ModelAdmin):
    list_display = ("number", "title")
    search_fields = ("title",)
    ordering = ("number",)


@admin.register(Sector)
class SectorAdmin(ModelAdmin):
    list_display = ("name", "parent", "sdg_goal", "is_active")
    list_filter = ("is_active", "sdg_goal")
    search_fields = ("name", "slug")
    ordering = ("name",)


@admin.register(Theme, ApplicantType)
class TaxonomyAdmin(ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    ordering = ("name",)


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "object_id")
    list_filter = ("action", "object_type")
    search_fields = ("object_type", "object_id", "action")
    readonly_fields = ("actor", "action", "object_type", "object_id", "changes", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AuditLog | None = None) -> bool:
        return False
