from typing import TYPE_CHECKING, Any

__all__ = ["UnfoldModelAdmin", "UnfoldTabularInline"]

if TYPE_CHECKING:
    from django.contrib.admin import ModelAdmin as DjangoModelAdmin
    from django.contrib.admin import TabularInline as DjangoTabularInline

    class UnfoldModelAdmin(DjangoModelAdmin[Any]):
        pass

    class UnfoldTabularInline(DjangoTabularInline[Any, Any]):
        pass
else:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin  # noqa: F401
    from unfold.admin import TabularInline as UnfoldTabularInline  # noqa: F401
