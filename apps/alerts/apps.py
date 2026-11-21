from django.apps import AppConfig


class AlertsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.alerts"

    def ready(self) -> None:
        import apps.alerts.signals  # noqa: F401
