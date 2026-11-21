from django.urls import path

from apps.alerts import views

app_name = "alerts"

urlpatterns = [
    path("saved-searches/", views.saved_searches, name="saved-searches"),
    path("saved-searches/save/", views.save_search, name="save-search"),
    path("alerts/<int:pk>/", views.update_alert, name="update-alert"),
    path("saved-searches/<int:pk>/delete/", views.delete_saved_search, name="delete-search"),
]
