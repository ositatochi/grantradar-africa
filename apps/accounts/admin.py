from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import User
from apps.core.admin_types import UnfoldModelAdmin as ModelAdmin


@admin.register(User)
class GrantRadarUserAdmin(UserAdmin, ModelAdmin):  # type: ignore[type-arg]
    pass
