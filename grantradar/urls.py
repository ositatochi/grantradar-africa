from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import include, path


def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", include("apps.search.urls")),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
]
