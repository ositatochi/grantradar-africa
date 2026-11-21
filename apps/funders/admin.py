from django.contrib import admin

from apps.core.admin_types import UnfoldModelAdmin as ModelAdmin
from apps.funders.models import Funder


@admin.register(Funder)
class FunderAdmin(ModelAdmin):
    list_display = ("name", "funder_type", "website", "is_active")
    list_filter = ("funder_type", "is_active")
    search_fields = ("name", "description")
    filter_horizontal = ("countries", "sectors")
