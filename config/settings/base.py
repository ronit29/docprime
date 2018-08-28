"""
Django settings for test project.

Generated by 'django-admin startproject' using Django 2.0.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import environ
import datetime
import json
import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
#BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = environ.Path(__file__) - 3
APPS_DIR = ROOT_DIR.path('ondoc')

env = environ.Env()

READ_DOT_ENV_FILE = env.bool('DJANGO_READ_DOT_ENV_FILE', default=True)

if READ_DOT_ENV_FILE:
    if(env('DJANGO_SETTINGS_MODULE')=='config.settings.production' or env('DJANGO_SETTINGS_MODULE')=='config.settings.staging'):
        env.read_env(str(ROOT_DIR.path('.env')))
    if(env('DJANGO_SETTINGS_MODULE')=='config.settings.local'):
        env.read_env(str(ROOT_DIR.path('.env.local')))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# Custom User model
AUTH_USER_MODEL = 'authentication.User'
AUTHENTICATION_BACKENDS = ('ondoc.authentication.backends.AuthBackend',)

SECRET_KEY = env('DJANGO_SECRET_KEY')

JWT_AUTH = {
    'JWT_VERIFY': True,
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_AUTH_HEADER_PREFIX': 'Token',
    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),
}

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DJANGO_DEBUG', False)

TIME_ZONE = 'Asia/Kolkata'

LANGUAGE_CODE = 'en-us'

USE_I18N = True

USE_L10N = True

USE_TZ = True

FILE_UPLOAD_PERMISSIONS = 0o664
# FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases


DATABASES = {
    'default': env.db('DATABASE_URL'),
}
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'



# Application definition

DJANGO_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'collectfast',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'reversion',
    'storages',

)

THIRD_PARTY_APPS = (

    'rest_framework',
    'rest_framework.authtoken',
    'crispy_forms',
    'corsheaders',
    'import_export',
    'dal',
    'dal_select2',
    'django_tables2',
    'anymail',
    'nested_admin'
)

LOCAL_APPS = (
    'ondoc.crm',
    'ondoc.authentication',
    'ondoc.doctor',
    'ondoc.diagnostic',
    'ondoc.onboard',
    'ondoc.lead',
    'ondoc.chat',
    'ondoc.notification',
    'ondoc.account',
    'ondoc.insurance',
    'ondoc.coupon',
    'ondoc.payout',
    'ondoc.web',
    'ondoc.matrix',
    'ondoc.articles',
    'ondoc.reports',
)

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'ondoc.articles.middleware.CsrfGetParamMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ORIGIN_ALLOW_ALL = True

ROOT_URLCONF = 'config.urls'

WSGI_APPLICATION = 'config.wsgi.application'




# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_ROOT = str(ROOT_DIR('static'))

STATIC_URL = '/static/'

STATICFILES_DIRS = (
    str(APPS_DIR.path('static')),
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

MEDIA_URL = '/media/'
MEDIA_ROOT = str(APPS_DIR('media'))

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # https://docs.djangoproject.com/en/dev/ref/settings/#template-dirs
        'DIRS': [
            str(APPS_DIR.path('templates')),
        ],
        'OPTIONS': {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-debug
            'debug': DEBUG,
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-loaders
            # https://docs.djangoproject.com/en/dev/ref/templates/api/#loader-types
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
                ]),

            ],
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'ondoc.web.context_processors.google_analytics',
            ],
        },
    },
]

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'PAGE_SIZE': 10,
    'COERCE_DECIMAL_TO_STRING': True,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        #'rest_framework.authentication.SessionAuthentication',
        # 'rest_framework.authentication.TokenAuthentication',
        # 'ondoc.authentication.auth.CustomAuthentication',
        # 'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
        'ondoc.authentication.backends.JWTAuthentication',
    ),
    'EXCEPTION_HANDLER': 'ondoc.api.v1.utils.custom_exception_handler',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    )

}
MAP_WIDGETS = {
    "GooglePointFieldWidget": (
        ("zoom", 15),
        ("mapCenterLocationName", "gurgaon"),
        ("GooglePlaceAutocompleteOptions", {'componentRestrictions': {'country': 'in'}}),
        ("markerFitZoom", 12),
    ),
    "GOOGLE_MAP_API_KEY": "AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA"
}

GOOGLE_MAPS_API_KEY = 'AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA'


CRISPY_TEMPLATE_PACK = 'bootstrap3'
SMS_AUTH_KEY = env('SMS_AUTH_KEY')

RABBITMQ_CONNECTION_SETTINGS = {
    'CONNECTION_URL': env('RABBITMQ_CONNECTION_URL'),
    'NOTIFICATION_QUEUE': env('RABBITMQ_NOTIFICATION_QUEUE')
}
CELERY_BROKER_URL = env('RABBITMQ_CONNECTION_URL')

BASE_URL = env('BASE_URL')
ADMIN_BASE_URL = env('ADMIN_BASE_URL')
CONSUMER_APP_DOMAIN = env('CONSUMER_APP_DOMAIN')
API_BASE_URL = env('API_BASE_URL')

MATRIX_AUTH_TOKEN = env('MATRIX_USER_TOKEN')
CHAT_API_URL = env('CHAT_API_URL')
PG_SECRET_KEY_P1 = env('PG_SECRET_KEY_P1')
PG_CLIENT_KEY_P1 = env('PG_CLIENT_KEY_P1')
PG_SECRET_KEY_P2 = env('PG_SECRET_KEY_P2')
PG_CLIENT_KEY_P2 = env('PG_CLIENT_KEY_P2')
PG_SECRET_KEY_REFUND = env('PG_SECRET_KEY_REFUND')
PG_CLIENT_KEY_REFUND = env('PG_CLIENT_KEY_REFUND')
PG_REFUND_URL = env('PG_REFUND_URL')
PG_REFUND_AUTH_TOKEN = env('PG_REFUND_AUTH_TOKEN')
AUTO_CANCEL_OPD_DELAY = 30  # In min
AUTO_CANCEL_LAB_DELAY = 30  # In min
OPS_EMAIL_ID = env.list('OPS_EMAIL_ID')
AUTO_REFUND = env.bool('AUTO_REFUND')

ANYMAIL = {
    "MAILGUN_API_KEY": env('MAILGUN_API_KEY', default=None),
    "MAILGUN_SENDER_DOMAIN": 'mail.docprime.com',
}

DEFAULT_FROM_EMAIL = "support@docprime.com"

API_ENABLED = env('API_ENABLED', default=False)
SEND_THROUGH_NODEJS_ENABLED = env.bool('SEND_THROUGH_NODEJS_ENABLED', default=False)

#Config for AWS S3 bucket
#MEDIA_URL = '/media/'
#AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
#AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
#AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
#AWS_QUERYSTRING_AUTH = False
#S3_USE_SIGV4 = True
#AWS_S3_REGION_NAME='ap-south-1'
# AWS_S3_ENCRYPTION = True
# AWS_S3_OBJECT_PARAMETERS = {
#     'CacheControl': 'max-age=86400',
# }
#
# MEDIA_URL = 'http://%s.s3.amazonaws.com/media/' % AWS_STORAGE_BUCKET_NAME
# MEDIA_ROOT = str(APPS_DIR('media'))
#
#DEFAULT_FILE_STORAGE = 'config.settings.storage_backends.MediaStorage'
#DJANGO_TABLES2_TEMPLATE = 'django_tables2/bootstrap.html'
