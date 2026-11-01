"""XPRISM: Django settings.

All deployment-specific values come from environment variables (see deploy/env.example).
With no environment set, the project runs in local development mode on SQLite.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ('1', 'true', 'yes', 'on')


# Load KEY=VALUE pairs from a .env file next to manage.py (no extra dependency needed)
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# Safe by default: debug is OFF unless DJANGO_DEBUG=true (set it only on your own computer).
DEBUG = env_bool('DJANGO_DEBUG', False)
_TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'
SECRET_KEY = env('DJANGO_SECRET_KEY') or ('dev-only-insecure-key-change-me' if (DEBUG or _TESTING) else None)
if not SECRET_KEY:
    raise RuntimeError('DJANGO_SECRET_KEY is not set. Copy deploy/env.example to .env and fill it in (or set DJANGO_DEBUG=true for local development).')
ALLOWED_HOSTS = [h.strip() for h in env('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'lab',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'lab.middleware.AccountGateMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'lab.context.site',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'

if env('POSTGRES_DB'):
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB'), 'USER': env('POSTGRES_USER', 'xprism'),
        'PASSWORD': env('POSTGRES_PASSWORD', ''), 'HOST': env('POSTGRES_HOST', '127.0.0.1'),
        'PORT': env('POSTGRES_PORT', '5432'), 'CONN_MAX_AGE': 60,
    }}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / env('SQLITE_NAME', 'db.sqlite3')}}

# shared across gunicorn workers (login throttling)
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.db.DatabaseCache', 'LOCATION': 'mcp_cache'}}

AUTH_USER_MODEL = 'lab.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'landing'

LANGUAGE_CODE = 'en-in'
TIME_ZONE = env('DJANGO_TIME_ZONE', 'Asia/Kolkata')
USE_I18N = False
USE_TZ = True

STATIC_URL = '/assets/'
STATICFILES_DIRS = [BASE_DIR / 'static' / 'assets']
STATIC_ROOT = Path(env('DJANGO_STATIC_ROOT', BASE_DIR / 'staticfiles'))
EXPERIMENTS_DIR = BASE_DIR / 'experiments'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# e-mail (password reset). Console backend until SMTP is configured.
if env('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST'); EMAIL_PORT = int(env('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', ''); EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'XPRISM <no-reply@localhost>')

# sessions & security
SESSION_COOKIE_AGE = 60 * 60 * 10          # 10 h: a lab day
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'SAMEORIGIN'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool('DJANGO_SECURE_COOKIES', True)
    CSRF_COOKIE_SECURE = env_bool('DJANGO_SECURE_COOKIES', True)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', False)   # nginx normally does the redirect
    SECURE_HSTS_SECONDS = int(env('DJANGO_HSTS_SECONDS', '0'))

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': env('DJANGO_LOG_LEVEL', 'WARNING')},
}

# ---------------------------------------------------------------- site / legal
SITE_NAME = 'XPRISM'
SITE_FULL_NAME = 'Experimental Pharmacology Research & Interactive Student Module'
SITE_TAGLINE = env('SITE_TAGLINE', SITE_FULL_NAME)
SITE_DEFAULT_LOCATION = env('SITE_DEFAULT_LOCATION', 'Aaron Innovations')
SITE_CREATOR = 'Dr. Vara Prasad Saka'
SITE_CREATOR_EMAIL = env('SITE_CREATOR_EMAIL', 'drvaraprasadsaka@gmail.com')
SITE_INSTITUTION = 'Aaron Innovations'
SITE_AIM_SHORT = ('Putting the 3Rs (Replacement, Reduction and Refinement) into practice by giving students '
                  'realistic, interactive alternatives to animal experiments.')
SITE_AIM = ('XPRISM exists to put the 3Rs (Replacement, Reduction and Refinement) into everyday practice in '
            'pharmacology education. It gives students realistic, interactive alternatives to animal experiments, '
            'so that practical skills can be learned without harming animals, and it builds a lasting habit of '
            'ethical, responsible research in line with CCSEA and PCI guidelines.')
SITE_URL = env('SITE_URL', 'http://localhost:8000')
# Legal entity shown in the Privacy Policy / Terms. Fill these in deploy/.env before going live.
LEGAL = {
    'org_name': env('LEGAL_ORG_NAME', 'Aaron Innovations'),
    'org_address': env('LEGAL_ORG_ADDRESS', 'Rajouri Garden, New Delhi, India'),
    'contact_email': env('LEGAL_CONTACT_EMAIL', 'drvaraprasadsaka@gmail.com'),
    'grievance_officer': env('LEGAL_GRIEVANCE_OFFICER', 'Dr. Vara Prasad Saka'),
    'grievance_email': env('LEGAL_GRIEVANCE_EMAIL', 'drvaraprasadsaka@gmail.com'),
    'jurisdiction': env('LEGAL_JURISDICTION', 'New Delhi, India'),
    'hosting_location': env('LEGAL_HOSTING_LOCATION', 'India'),
}
# Bump when the Privacy Policy / Terms change: every user is asked to accept again.
POLICY_VERSION = '2026-11-02'
POLICY_EFFECTIVE = '2 November 2026'
# Trial rules & animal-ethics agreement shown as a pop-up after sign-in (bump to ask everyone again)
ETHICS_VERSION = '2026-11-02'
# a free-trial visit ends when the user returns to the lab index / a dashboard, opens another module, or after this many hours
TRIAL_VISIT_MAX_HOURS = int(env('TRIAL_VISIT_MAX_HOURS', '3'))
SUBSCRIPTION_CONTACT = env('SUBSCRIPTION_CONTACT', 'drvaraprasadsaka@gmail.com')
DATA_RETENTION_YEARS = int(env('DATA_RETENTION_YEARS', '3'))
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_MINUTES = 15
