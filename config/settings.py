"""
Django settings for the 営業機会アラートツール (Sales Opportunity Alert Tool) — FREE版 MVP.

Configuration is environment-variable driven so the same codebase runs
locally (SQLite, console email) and in production (Postgres via
DATABASE_URL, Gmail SMTP) without code changes — see 技術設計書 section 1/5/6.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # ローカル開発用。本番はホスティング側の環境変数を使用する。


def env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-production",
)

DEBUG = env_bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "companies",
    "intel",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database -----------------------------------------------------------
# Local/dev: SQLite by default. Production: set DATABASE_URL to a Postgres
# connection string (e.g. from Neon) and it takes over automatically.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "accounts:login"

# --- i18n / timezone ------------------------------------------------------
# ユーザーは日本国内企業を想定しているため、表示・スケジュール判定は Asia/Tokyo を基準にする。
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG else (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Email (design doc section 5) -----------------------------------------
# 初期版は Gmail SMTP を利用。EMAIL_BACKEND / SMTP接続情報はすべて環境変数化してあり、
# 将来 SendGrid / AWS SES 等へ切り替える際もコード変更不要（.env のみ変更すればよい）。
if env_bool("EMAIL_USE_CONSOLE", default=DEBUG and not os.environ.get("EMAIL_HOST_USER")):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")  # Gmailの場合はアプリパスワードを設定
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "alerts@example.com")

# --- App-specific settings --------------------------------------------
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost:8000")

# 元設計書30章: FREEプランの監視企業数上限（例：100社）
FREE_PLAN_COMPANY_LIMIT = int(os.environ.get("FREE_PLAN_COMPANY_LIMIT", "100"))

# 情報鮮度加点（元設計書15章）。設定画面からの編集要件が明記されていないため、
# 現時点ではアプリ設定値として保持し、将来DBテーブル化しやすい形（リストオブディクト）にしておく。
FRESHNESS_SCORE_RULES = [
    {"max_days": 7, "score": 20},
    {"max_days": 30, "score": 10},
    {"max_days": 90, "score": 5},
]

# クロール礼儀（技術設計書3.3節）
CRAWLER_USER_AGENT = os.environ.get(
    "CRAWLER_USER_AGENT",
    "OppRadarBot/1.0 (+mailto:{})".format(os.environ.get("CRAWLER_CONTACT_EMAIL", "contact@example.com")),
)
CRAWLER_MIN_DOMAIN_INTERVAL_SECONDS = float(os.environ.get("CRAWLER_MIN_DOMAIN_INTERVAL_SECONDS", "3"))
CRAWLER_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("CRAWLER_REQUEST_TIMEOUT_SECONDS", "10"))
CRAWLER_MAX_RETRIES = int(os.environ.get("CRAWLER_MAX_RETRIES", "2"))
CRAWLER_CIRCUIT_BREAKER_FAILURES = int(os.environ.get("CRAWLER_CIRCUIT_BREAKER_FAILURES", "5"))
CRAWLER_BATCH_SIZE = int(os.environ.get("CRAWLER_BATCH_SIZE", "25"))
