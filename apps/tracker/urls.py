from django.urls import path

from apps.tracker import views

app_name = "tracker"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("bookmarks/<int:opportunity_id>/", views.toggle_bookmark, name="bookmark-toggle"),
    path("opportunities/<int:opportunity_id>/add/", views.add_to_pipeline, name="pipeline-add"),
    path("items/<int:pk>/", views.item_detail, name="item-detail"),
    path("items/<int:pk>/remove/", views.remove_from_pipeline, name="remove-item"),
    path("calendar.ics", views.calendar_ics, name="calendar-ics"),
]
