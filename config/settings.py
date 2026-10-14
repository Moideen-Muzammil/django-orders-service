"""12-factor style settings: everything environment-specific comes from env vars."""
import os

# Fail fast if missing: a pod without a SECRET_KEY should crash at start, not run insecurely.
SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost").split(",")

INSTALLED_APPS = ["orders"]

MIDDLEWARE = [
    "config.middleware.HealthCheckMiddleware",  # must be FIRST (see middleware.py)
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Stateless service for this exercise. In production: Cloud SQL via the Auth Proxy.
DATABASES = {}

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Log to stdout: GKE ships container stdout to Cloud Logging automatically.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
