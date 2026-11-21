from django.contrib import admin

from apps.alerts.models import Alert, AlertDelivery, SavedSearch


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "owner", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "query", "owner__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["saved_search", "frequency", "channel", "is_active", "consent_given_at"]
    list_filter = ["frequency", "channel", "is_active"]
    search_fields = ["saved_search__name", "saved_search__owner__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AlertDelivery)
class AlertDeliveryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["alert", "status", "scheduled_at", "delivered_at"]
    list_filter = ["status", "scheduled_at"]
    search_fields = ["alert__saved_search__name", "alert__saved_search__owner__email"]
    readonly_fields = ["scheduled_at", "delivered_at", "error_message", "opportunity_ids"]
