from django.conf import settings
from django.http import HttpRequest


def account_features(request: HttpRequest) -> dict[str, bool]:
    del request
    return {"google_oauth_enabled": settings.GOOGLE_OAUTH_ENABLED}
