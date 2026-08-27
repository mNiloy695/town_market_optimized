"""
Centralized configuration for the Town Market project.

All settings are exported from this module and sourced from environment
variables via django-environ / python-decouple.

Usage:
    from core.config import SMS_API_KEY, SHIPPING_FEE, DEBUG
    OR
    from core.cloudflare import r2, is_r2_configured, get_service_status  # Cloudflare services
    OR
    from django.conf import settings  # (settings now re-exports from config)
"""

import os
from decimal import Decimal
from pathlib import Path

from django.conf import settings


# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent


# Environment mode
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')


#  Debug mode
DEBUG = bool(os.getenv('DEBUG', '0'))


# Allowed hosts
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
]


#  CORS settings
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only allow all in development
CORS_ALLOWED_ORIGINS = [
    s.strip() for s in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if s.strip()
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'https://overrigged-botanically-lila.ngrok-free.dev,'
        'http://172.24.0.1:3000,'
        'http://localhost:3000'
    ).split(',')
]


# Import Cloudflare services configuration
# Centralized Cloudflare service settings - easy to manage and switch
# All Cloudflare settings are available via core.cloudflare module
try:
    from core.cloudflare import r2, is_r2_configured, get_service_status, R2
except ImportError:
    # Fallback if cloudflare module not available
    r2 = None
    is_r2_configured = lambda: False
    get_service_status = lambda: {}
    R2 = None
    r2 = None

#  Cloudflare R2 Storage Configuration
# Derived from core.cloudflare module - central point for R2 management
# All R2 settings are available via: from core.cloudflare import r2, CLOUDFLARE_R2_*

#  R2 bucket name and account ID - from environment or defaults
CLOUDFLARE_R2_ACCOUNT_ID = os.getenv(
    'CLOUDFLARE_R2_ACCOUNT_ID',
    default='104dbc5609bc33780236c732ecf740dd'
)
CLOUDFLARE_R2_ACCESS_KEY_ID = os.getenv(
    'CLOUDFLARE_R2_ACCESS_KEY_ID',
    default=''
)
CLOUDFLARE_R2_SECRET_ACCESS_KEY = os.getenv(
    'CLOUDFLARE_R2_SECRET_ACCESS_KEY',
    default=''
)
CLOUDFLARE_R2_BUCKET_NAME = os.getenv(
    'CLOUDFLARE_R2_BUCKET_NAME',
    default='townmarket'
)

#  Optional: Custom CNAME pointing to R2 bucket
CLOUDFLARE_R2_CUSTOM_DOMAIN = os.getenv(
    'CLOUDFLARE_R2_CUSTOM_DOMAIN',
    default=''
)

#  R2 instance - for programmatic access
# Use: r2 = CLOUDFLARE_R2_INSTANCE or from core.cloudflare import r2
CLOUDFLARE_R2_INSTANCE = r2

#  Convenience: Check if R2 is properly configured
CLOUDFLARE_R2_CONFIGURED = is_r2_configured()

#  Convenience: Get full R2 service status
CLOUDFLARE_R2_SERVICE_STATUS = get_service_status()


#  SMS Configuration - Bangladeshi SMS Service
SMS_API_URL = os.getenv('SMS_API_URL', 'https://sms.corp.com.bd/api.php')
SMS_API_KEY = os.getenv('SMS_API_KEY', '')
SMS_SENDER_ID = os.getenv('SMS_SENDER_ID', '8809617635077')


# Core business settings
SHIPPING_FEE = int(os.getenv('SHIPPING_FEE', '50'))
ORDER_PAYMENT_TIMEOUT_MINUTES = int(os.getenv('ORDER_PAYMENT_TIMEOUT_MINUTES', '5'))
STORE_ID = os.getenv('STORE_ID', '')
STORE_PASSWORD = os.getenv('STORE_PASSWORD', '')


#  SSLCommerz URLs
SSLCOMMERZ_API_URL = os.getenv(
    'SSLCOMMERZ_API_URL',
    'https://sandbox.sslcommerz.com/gwprocess/v4/api.php',
)
SSLCOMMERZ_VALIDATION_URL = os.getenv(
    'SSLCOMMERZ_VALIDATION_URL',
    'https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php',
)


#  bKash Payment Gateway settings
BKASH_APP_KEY = os.getenv('BKASH_APP_KEY', '')
BKASH_APP_SECRET = os.getenv('BKASH_APP_SECRET', '')
BKASH_BASE_URL = os.getenv(
    'BKASH_BASE_URL',
    'https://sandbox.pay.bka.sh/v1.2.0-beta',
)


# Commission percentage
COMMISSION_PERCENTAGE = Decimal(os.getenv('commission_percentage', '0.10'))


#  JWT settings
ACCESS_TOKEN_LIFETIME = int(os.getenv('ACCESS_TOKEN_LIFETIME_DAYS', '5'))
REFRESH_TOKEN_LIFETIME = int(os.getenv('REFRESH_TOKEN_LIFETIME_DAYS', '7'))


#  Redis / Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/1')
CELERY_TIMEZONE = os.getenv('CELERY_TIMEZONE', 'Asia/Dhaka')


#  Database
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    default='sqlite:///db.sqlite3',
)


#  Password validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


#  Timezone & Language
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static & Media
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = BASE_DIR / "staticfiles"


#  Cloudflare R2 Storage Configuration
# These strings are required by Django's settings system
# They can be overridden via core.cloudflare module settings
DEFAULT_FILE_STORAGE = 'storages.backends.cloudflare.CloudFileStorage'
STATICFILES_STORAGE = 'storages.backends.cloudflare.StaticCloudFileStorage'
AWS_S3_FILE_OVERWRITE = False
DEFAULT_FILE_ACL = 'public-read'


#  Installed apps
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'phonenumber_field',
    'channels',
    'shop',
    'django_filters',
    'product',
    'cart',
    'order',
    'invoice',
    'review',
    'chat',
    'corsheaders',
]


#  Middleware
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


#  REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '120/minute',
    },
}