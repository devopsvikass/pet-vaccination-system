from pathlib import Path
from datetime import timedelta
import os
import secrets
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Lightweight .env loader (no external dependency required).
env_file = BASE_DIR / ".env"
if env_file.exists():
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

DEBUG = os.getenv("DEBUG", "True").strip().lower() in {"1", "true", "yes", "on"}

# Never use a committed fallback for a signing key. Local development gets a
# unique key persisted only in the ignored backend/.env file; deployments must
# provide the key through their secret manager/environment.
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY or SECRET_KEY == "generate-a-unique-secret-key-before-running":
    if DEBUG:
        SECRET_KEY = secrets.token_urlsafe(64)
        env_lines = env_file.read_text().splitlines() if env_file.exists() else []
        key_line = f"SECRET_KEY={SECRET_KEY}"
        for index, line in enumerate(env_lines):
            if line.strip().startswith("SECRET_KEY="):
                env_lines[index] = key_line
                break
        else:
            env_lines.append(key_line)
        env_file.write_text("\n".join(env_lines).rstrip() + "\n")
        try:
            os.chmod(env_file, 0o600)
        except OSError:
            pass
        os.environ["SECRET_KEY"] = SECRET_KEY
    else:
        raise ImproperlyConfigured(
            "Set a unique SECRET_KEY in the deployment environment."
        )

if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Set a unique SECRET_KEY in backend/.env or the deployment environment."
    )

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "pet-backend-service",
    "pet-frontend-service",
    "192.168.49.2",
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',
    'django_crontab',

    'accounts',
    'pets',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = 'backend.urls'

# MySQL is the only supported database backend. Reject any other configured
# engine rather than silently using a different database.
DB_ENGINE = os.getenv("DB_ENGINE", "mysql").strip().lower()
if DB_ENGINE != "mysql":
    raise ValueError("DB_ENGINE must be 'mysql'; this project requires MySQL.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "pet_vaccination_db"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

AUTH_USER_MODEL = 'accounts.User'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
}

STATIC_URL = 'static/'
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "15"))
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("Choose either EMAIL_USE_TLS or EMAIL_USE_SSL, not both.")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
# Gmail displays app passwords in groups separated by spaces; SMTP expects the
# same password without those formatting spaces.
EMAIL_HOST_PASSWORD = "".join(os.getenv("EMAIL_HOST_PASSWORD", "").split())
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)


CRONJOBS = [
    ('*/1 * * * *', 'pets.cron.send_vaccination_reminders'),
]
