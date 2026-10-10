"""
Django settings for CampusSwap.

Defaults are tuned for a local classroom demo (SQLite, console email,
DEBUG on). Override with environment variables for anything else:
    DJANGO_DEBUG=0  DJANGO_SECRET_KEY=...  DJANGO_ALLOWED_HOSTS=example.com
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-campusswap-key-change-me-before-deploying-0a9f8e7d6c5b4a",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Local apps
    "accounts.apps.AccountsConfig",
    "market.apps.MarketConfig",
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

ROOT_URLCONF = "campusswap_site.urls"

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
                "market.context_processors.navbar",
            ],
        },
    },
]

WSGI_APPLICATION = "campusswap_site.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Log in with either username or student email.
AUTHENTICATION_BACKENDS = [
    "accounts.backends.UsernameOrEmailBackend",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "market:home"
LOGOUT_REDIRECT_URL = "market:home"

LANGUAGE_CODE = "en-ca"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password-reset emails print to the terminal during the demo.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "CampusSwap <no-reply@campusswap.local>"

# Messages framework -> Bootstrap alert classes
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

# ---- CampusSwap rules ---------------------------------------------------
# "Student-only": sign-up requires an email ending in one of these.
# Put your college's domain first, e.g. ("georgebrown.ca",).
STUDENT_EMAIL_DOMAINS = tuple(
    d.strip().lower()
    for d in os.environ.get("CAMPUSSWAP_EMAIL_DOMAINS", ".ca,.edu").split(",")
    if d.strip()
)
MAX_LISTING_PHOTOS = 5
MAX_PHOTO_MB = 5
LISTINGS_PER_PAGE = 12
RECENTLY_VIEWED_MAX = 8
# Listings with this many open reports are hidden automatically until an admin reviews them.
AUTO_HIDE_REPORT_THRESHOLD = 3

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
