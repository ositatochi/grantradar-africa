from django.contrib import admin

from apps.tracker.models import Bookmark, DeadlineReminder, Note, PipelineItem

admin.site.register(Bookmark)
admin.site.register(PipelineItem)
admin.site.register(Note)


@admin.register(DeadlineReminder)
class DeadlineReminderAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["pipeline_item", "deadline_date", "days_before", "status", "sent_at"]
    list_filter = ["status", "days_before"]
    readonly_fields = ["sent_at", "error_message"]
