import os
from pathlib import Path
from typing import Any

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "local-only-insecure-key-do-not-use-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1",
).split(",")
CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin
]

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "apps.accounts",
    "apps.core",
    "apps.funders",
    "apps.sources",
    "apps.crawler",
    "apps.pipeline",
    "apps.opportunities",
    "apps.alerts",
    "apps.tracker",
    "apps.teams",
    "apps.api",
    "apps.search.apps.SearchConfig",
    "apps.resources",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "grantradar.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "grantradar.wsgi.application"
ASGI_APPLICATION = "grantradar.asgi.application"

if os.environ.get("DJANGO_TEST_SQLITE") == "1":
    DATABASES: dict[str, Any] = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "grantradar-tests",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "grantradar"),
            "USER": os.environ.get("POSTGRES_USER", "grantradar"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "change-this-local-password"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ.get("REDIS_CACHE_URL", "redis://localhost:6379/2"),
            "KEY_PREFIX": "grantradar",
        }
    }

AUTH_USER_MODEL = "accounts.User"
UNFOLD = {
    "SITE_TITLE": "GrantRadar Africa",
    "SITE_HEADER": "GrantRadar Africa",
    "SITE_URL": "/",
}

LANGUAGE_CODE = "en"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEILI_URL = os.environ.get("MEILI_URL", "")
MEILI_MASTER_KEY = os.environ.get("MEILI_MASTER_KEY", "")

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND",
    "redis://localhost:6379/1",
)
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "crawl-due-sources-every-15-minutes": {
        "task": "apps.crawler.tasks.crawl_due_sources",
        "schedule": crontab(minute="*/15"),
    },
    "process-pending-documents-every-five-minutes": {
        "task": "apps.pipeline.tasks.process_pending_documents",
        "schedule": crontab(minute="*/5"),
    },
    "expire-opportunities-daily": {
        "task": "apps.pipeline.tasks.expire_opportunities",
        "schedule": crontab(minute=0, hour=1),
    },
}
