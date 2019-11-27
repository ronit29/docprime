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
from mongoengine import *
from pymongo.read_preferences import ReadPreference

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
    'JWT_EXPIRATION_DELTA': datetime.timedelta(days=365),
    'JWT_AUTH_HEADER_PREFIX': 'Token',
    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=365),
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

DATABASE_ROUTERS = ['config.settings.db_router.DatabaseRouter']
DATABASES = {
    'default': env.db('DATABASE_URL'),
}
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

if(env('DJANGO_SETTINGS_MODULE')=='config.settings.production'):
    DATABASES['slave'] = env.db('SLAVE_DATABASE_URL') if env.db('SLAVE_DATABASE_URL') else env.db('DATABASE_URL')
    DATABASES['slave']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'


# if (env('DJANGO_SETTINGS_MODULE') == 'config.settings.production'):
#     DATABASES['doc_read'] = env.db('READ_DATABASE_URL')
#     DATABASES['doc_read']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

# try:
#     if env('MSSQL_HOST') and env('MSSQL_USERNAME') and env('MSSQL_PASSWORD'):
#         DATABASES['sql_server'] = {
#              'ENGINE': 'sql_server.pyodbc',
#              'HOST': env('MSSQL_HOST'),
#              'USER': env('MSSQL_USERNAME'),
#              'PASSWORD': env('MSSQL_PASSWORD'),
#              'NAME': env('MSSQL_DB'),
#              'OPTIONS': {
#                   'driver' : 'ODBC Driver 17 for SQL Server'
#             }
#         }
# except Exception as e:
#     print(str(e))




try:
    MONGO_STORE = False
    if env('MONGO_DB_NAME') and env('MONGO_DB_HOST') and env('MONGO_DB_PORT'):
        mongo_port = int(env('MONGO_DB_PORT'))
        if env('MONGO_DB_USERNAME', None) and env('MONGO_DB_PASSWORD', None):
            # connect(env('MONGO_DB_NAME'), host=env('MONGO_DB_HOST'), port=mongo_port, username=env('MONGO_DB_USERNAME'),
            #                                 password=env('MONGO_DB_PASSWORD'), authentication_source='admin')
            connect(host=env('MONGO_CONNECTION_STRING'), read_preference=ReadPreference.PRIMARY_PREFERRED)
            # host = 'mongodb://' + env('MONGO_DB_USERNAME') + ':' + env('MONGO_DB_PASSWORD') + '@' + 10.20.5.148:27017,10.20.6.116:27017/DocPrimeLogs?replicaSet=rs5'
            # connect(host='mongodb://ankitPBpyuser:ajd87GHSd@10.20.5.148:27017,10.20.6.116:27017/DocPrimeLogs?replicaSet=rs5', authentication_source='admin')

        else:
            connect(env('MONGO_DB_NAME'), host=env('MONGO_DB_HOST'), port=mongo_port)
        MONGO_STORE = env.bool('MONGO_STORE', default=False)
except Exception as e:
    print(e)
    print('Failed to connect to mongo')
    MONGO_STORE = False

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
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'reversion_compare',
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
    'nested_admin',
    'ipware',
    'django_user_agents',
    'fluent_comments',
    'threadedcomments',
    'django_comments',
    'safedelete',
    'qrcode',
    'Crypto',
    'multiselectfield',
    'django_select2',
    'geopy'
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
    'ondoc.location',
    'ondoc.common',
    'ondoc.tracking',
    'ondoc.seo',
    'ondoc.ratings_review',
    'ondoc.geoip',
    'ondoc.procedure',
    'ondoc.elastic',
    'ondoc.banner',
    'ondoc.cart',
    'ondoc.ckedit',
    'ondoc.integrations',
    'ondoc.screen',
    'ondoc.comments',
    'ondoc.subscription_plan',
    'ondoc.bookinganalytics',
    'ondoc.prescription',
    'ondoc.corporate_booking',
    'ondoc.salespoint',
    'ondoc.plus',
    'ondoc.provider',
)

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
ADD_REVERSION_ADMIN = True

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
    'django_user_agents.middleware.UserAgentMiddleware'
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

SITE_ID = 1

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # https://docs.djangoproject.com/en/dev/ref/settings/#template-dirs
        'DIRS': [
            str(APPS_DIR.path('static')),
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
        # 'rest_framework.authentication.SessionAuthentication',
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
    "GOOGLE_MAP_API_KEY": "AIzaSyDFxu_VGlmLojtgiwn892OYzV6IY_Inl6I"
}

# GOOGLE_MAPS_API_KEY = 'AIzaSyClYPAOTREfAZ-95eRbU6hDVHU0p3XygoY'
GOOGLE_MAPS_API_KEY = 'AIzaSyDFxu_VGlmLojtgiwn892OYzV6IY_Inl6I'


CRISPY_TEMPLATE_PACK = 'bootstrap3'
SMS_AUTH_KEY = env('SMS_AUTH_KEY')

RABBITMQ_CONNECTION_SETTINGS = {
    'CONNECTION_URL': env('RABBITMQ_CONNECTION_URL'),
    'NOTIFICATION_QUEUE': env('RABBITMQ_NOTIFICATION_QUEUE')
}
CELERY_BROKER_URL = env('RABBITMQ_CONNECTION_URL')
CELERY_QUEUE = env('CELERY_QUEUE',default='celery')

BASE_URL = env('BASE_URL')
ADMIN_BASE_URL = env('ADMIN_BASE_URL')
CONSUMER_APP_DOMAIN = env('CONSUMER_APP_DOMAIN')
PROVIDER_APP_DOMAIN = env('PROVIDER_APP_DOMAIN')

API_BASE_URL = env('API_BASE_URL')
REVERSE_GEOCODING_API_KEY = env('REVERSE_GEOCODING_API_KEY')
MATRIX_API_URL = env('MATRIX_API_URL')
MATRIX_STATUS_UPDATE_API_URL = env('MATRIX_STATUS_UPDATE_API_URL')
MATRIX_API_TOKEN = env('MATRIX_API_TOKEN')
MATRIX_AUTH_TOKEN = env('MATRIX_USER_TOKEN')
CHAT_API_URL = env('CHAT_API_URL')
CHAT_PRESCRIPTION_URL = env('CHAT_PRESCRIPTION_URL')
PG_SECRET_KEY_P1 = env('PG_SECRET_KEY_P1')
PG_CLIENT_KEY_P1 = env('PG_CLIENT_KEY_P1')
PG_SECRET_KEY_P2 = env('PG_SECRET_KEY_P2')
PG_CLIENT_KEY_P2 = env('PG_CLIENT_KEY_P2')
PG_SECRET_KEY_REFUND = env('PG_SECRET_KEY_REFUND')
PG_CLIENT_KEY_REFUND = env('PG_CLIENT_KEY_REFUND')
PG_REFUND_URL = env('PG_REFUND_URL')
PG_REFUND_AUTH_TOKEN = env('PG_REFUND_AUTH_TOKEN')
PG_DUMMY_TRANSACTION_URL = env('PG_DUMMY_TRANSACTION_URL')
PG_DUMMY_TRANSACTION_TOKEN = env('PG_DUMMY_TRANSACTION_TOKEN')
PG_REFUND_STATUS_API_URL = env('PG_REFUND_STATUS_API_URL')
PG_SETTLEMENT_URL = env('PG_SETTLEMENT_URL')
PG_PAYMENT_ACKNOWLEDGE_URL = env('PG_PAYMENT_ACKNOWLEDGE_URL')
PAYOUTS_ENABLED = env('PAYOUTS_ENABLED')
PG_REFUND_STATUS_POLL_TIME = 60  # In min
PG_PAYOUT_CLIENT_KEY = env('PG_PAYOUT_CLIENT_KEY')
PG_PAYOUT_SECRET_KEY = env('PG_PAYOUT_SECRET_KEY')
PG_SEAMLESS_CAPTURE_AUTH_TOKEN=env('PG_SEAMLESS_CAPTURE_AUTH_TOKEN')
PG_SEAMLESS_RELEASE_AUTH_TOKEN=env('PG_SEAMLESS_RELEASE_AUTH_TOKEN')
PG_CAPTURE_PAYMENT_URL = env('PG_CAPTURE_PAYMENT_URL')
PG_RELEASE_PAYMENT_URL = env('PG_RELEASE_PAYMENT_URL')
PAYMENT_AUTO_CAPTURE_DURATION=env('PAYMENT_AUTO_CAPTURE_DURATION', default=60) # In hours
REFUND_INACTIVE_TIME = 24  # In hours
AUTO_CANCEL_OPD_DELAY = 3000  # In min
AUTO_CANCEL_LAB_DELAY = 30  # In min
OPS_EMAIL_ID = env.list('OPS_EMAIL_ID')
IPD_PROCEDURE_CONTACT_DETAILS = env.list('IPD_PROCEDURE_CONTACT_DETAILS')
ORDER_FAILURE_EMAIL_ID = env.list('ORDER_FAILURE_EMAIL_ID')
AUTO_REFUND = env.bool('AUTO_REFUND')
HARD_CODED_OTP = '357237'
MAX_DIST_USER = 50  # In KM
MAXMIND_ACCOUNT_ID = env('MAXMIND_ACCOUNT_ID')
MAXMIND_LICENSE_KEY = env('MAXMIND_LICENSE_KEY')
MAXMIND_CITY_API_URL = env('MAXMIND_CITY_API_URL')
OTP_BYPASS_NUMBERS = env.list('OTP_BYPASS_NUMBERS')
TIME_BEFORE_APPOINTMENT_TO_SEND_OTP = env.int('TIME_BEFORE_APPOINTMENT_TO_SEND_OTP', default=60)  # in minutes
TIME_AFTER_APPOINTMENT_TO_SEND_CONFIRMATION = env.int('TIME_AFTER_APPOINTMENT_TO_SEND_CONFIRMATION', default=120)
TIME_AFTER_APPOINTMENT_TO_SEND_SECOND_CONFIRMATION = env.int('TIME_AFTER_APPOINTMENT_TO_SEND_SECOND_CONFIRMATION', default=1440)
TIME_AFTER_APPOINTMENT_TO_SEND_THIRD_CONFIRMATION = env.int('TIME_AFTER_APPOINTMENT_TO_SEND_THIRD_CONFIRMATION', default=2880)
# MONGO_URL = env.list('MONGO_URL')
#GOOGLE_MAP_API_KEY = env('GOOGLE_MAP_API_KEY')
PG_SECRET_KEY_P3 = env('PG_SECRET_KEY_P3')
PG_CLIENT_KEY_P3 = env('PG_CLIENT_KEY_P3')
GYNECOLOGIST_SPECIALIZATION_IDS = env('GYNECOLOGIST_SPECIALIZATION_IDS')
ONCOLOGIST_SPECIALIZATION_IDS = env('ONCOLOGIST_SPECIALIZATION_IDS')
MATRIX_NUMBER_MASKING = env('MATRIX_NUMBER_MASKING')
UPDATE_DOCTOR_SEARCH_SCORE_TIME = 24  # In hours
SYNC_ELASTIC = 24
THYROCARE_USERNAME=env('THYROCARE_USERNAME')
THYROCARE_PASSWORD=env('THYROCARE_PASSWORD')
THYROCARE_API_KEY=env('THYROCARE_API_KEY')
THYROCARE_BASE_URL=env('THYROCARE_BASE_URL')
THYROCARE_REF_CODE=env('THYROCARE_REF_CODE')
SAFE_DELETE_INTERPRET_UNDELETED_OBJECTS_AS_CREATED=env('SAFE_DELETE_INTERPRET_UNDELETED_OBJECTS_AS_CREATED')
NO_OF_WEEKS_FOR_TIME_SLOTS=env('NO_OF_WEEKS_FOR_TIME_SLOTS')
THYROCARE_INTEGRATION_ENABLED= env.bool('THYROCARE_INTEGRATION_ENABLED')
ORDER_SUMMARY_CRON_TIME = env('ORDER_SUMMARY_CRON_TIME')
THYROCARE_REPORT_CRON_TIME = env('THYROCARE_REPORT_CRON_TIME')
COUNT_DOWN_FOR_REMINDER=env('COUNT_DOWN_FOR_REMINDER')

NODAL_BENEFICIARY_API=env('NODAL_BENEFICIARY_API')
NODAL_BENEFICIARY_TOKEN=env('NODAL_BENEFICIARY_TOKEN')
BENE_STATUS_API=env('BENE_STATUS_API')
BENE_STATUS_TOKEN=env('BENE_STATUS_TOKEN')

SETTLEMENT_DETAILS_API=env('SETTLEMENT_DETAILS_API', default=None)
SETTLEMENT_AUTH=env('SETTLEMENT_AUTH', default=None)
THYROCARE_NAME_PARAM_REQUIRED_TESTS = env('THYROCARE_NAME_PARAM_REQUIRED_TESTS', default='')
IS_INSURANCE_ACTIVE = env.bool('IS_INSURANCE_ACTIVE')
IS_PLUS_ACTIVE = env.bool('IS_PLUS_ACTIVE')


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
DATA_UPLOAD_MAX_NUMBER_FIELDS=10000
CONN_MAX_AGE=600

AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')

PROVIDER_EMAIL = env('PROVIDER_EMAIL', default='')
INSURANCE_GYNECOLOGIST_LIMIT = 5
INSURANCE_ONCOLOGIST_LIMIT = 5

#comments Settings
COMMENTS_APP = 'fluent_comments'
SITE_ID = 1
FLUENT_COMMENTS_REPLACE_ADMIN = False
CONSUMER_ANDROID_MESSAGE_HASH = env('CONSUMER_ANDROID_MESSAGE_HASH', default='')
PROVIDER_ANDROID_MESSAGE_HASH = env('PROVIDER_ANDROID_MESSAGE_HASH', default='')
PARTNERS_INVOICE_ENCODE_KEY = env('PARTNERS_INVOICE_ENCODE_KEY', default='')
MATRIX_DOC_AUTH_TOKEN = env('MATRIX_DOC_AUTH_TOKEN')
INSURANCE_FLOAT_LIMIT_ALERT_EMAIL=env.list('INSURANCE_FLOAT_LIMIT_ALERT_EMAIL')
INSURANCE_MIS_EMAILS=env.list('INSURANCE_MIS_EMAILS')
INSURANCE_MIS_PASSWORD=env('INSURANCE_MIS_PASSWORD')
DEAL_AGREED_PRICE_CHANGE_EMAILS = env.list('DEAL_AGREED_PRICE_CHANGE_EMAILS')
LOGO_CHANGE_EMAIL_RECIPIENTS=env.list('LOGO_CHANGE_EMAIL_RECIPIENTS')

INSURANCE_SPECIALIZATION_WITH_DAYS_LIMIT=env('INSURANCE_SPECIALIZATION_WITH_DAYS_LIMIT')
DOCPRIME_NODAL2_MERCHANT=env('DOCPRIME_NODAL2_MERCHANT',default=None)
DEFAULT_FOLLOWUP_DURATION=7
INSURANCE_OPS_EMAIL=env.list('INSURANCE_OPS_EMAIL')
INSURANCE_CANCELLATION_APPROVAL_ALERT_TO_EMAIL=env('INSURANCE_CANCELLATION_APPROVAL_ALERT_TO_EMAIL')
INSURANCE_CANCELLATION_APPROVAL_ALERT_CC_EMAIL=env.list('INSURANCE_CANCELLATION_APPROVAL_ALERT_CC_EMAIL')
HOSPITALS_NOT_REQUIRED_UNIQUE_CODE=env('HOSPITALS_NOT_REQUIRED_UNIQUE_CODE')
MEDANTA_HOSPITAL_ID=env.int('MEDANTA_HOSPITAL_ID')
ARTEMIS_HOSPITAL_ID=env.int('ARTEMIS_HOSPITAL_ID')
WHATSAPP_AUTH_TOKEN=env('WHATSAPP_AUTH_TOKEN')
CHAT_IPD_DEPARTMENT_ID=env('CHAT_IPD_DEPARTMENT_ID', default='4TR2mqvL5MQiP6Eys')
CHAT_SOT_DEPARTMENT_ID=env('CHAT_SOT_DEPARTMENT_ID', default='nfu8AGssom3MhXtHw')
HOSPITAL_CREDIT_LETTER_REQUIRED = {
    'MEDANTA_HOSPITAL_ID': env.int('MEDANTA_HOSPITAL_ID'),
    'ARTEMIS_HOSPITAL_ID': env.int('ARTEMIS_HOSPITAL_ID')
}
CURRENT_FINANCIAL_YEAR=env('CURRENT_FINANCIAL_YEAR')
TDS_THRESHOLD_AMOUNT=env('TDS_THRESHOLD_AMOUNT')
TDS_APPLICABLE_RATE=env('TDS_APPLICABLE_RATE')
CONTACTUS_EMAILS=env.list('CONTACTUS_EMAILS')
LIST_APPOINTMENTS_VERSION_CHECK_IOS_GT=env.list('LIST_APPOINTMENTS_VERSION_CHECK_IOS_GT')
LIST_APPOINTMENTS_VERSION_CHECK_ANDROID_GT=env.list('LIST_APPOINTMENTS_VERSION_CHECK_ANDROID_GT')
DAILY_SCHEDULE_EXCLUDE_HOSPITALS=env('DAILY_SCHEDULE_EXCLUDE_HOSPITALS')
LEAD_VALIDITY_BUFFER_TIME = env.int('LEAD_VALIDITY_BUFFER_TIME', default=10)  # In mins
LEAD_AND_APPOINTMENT_BUFFER_TIME = env.int('LEAD_AND_APPOINTMENT_BUFFER_TIME', default=10)  # In mins
MEDICINE_TOP_SPECIALIZATIONS = env.list('MEDICINE_TOP_SPECIALIZATIONS')
MEDICINE_TOP_TESTS = env.list('MEDICINE_TOP_TESTS')
ROCKETCHAT_SERVER = env('ROCKETCHAT_SERVER')
ROCKETCHAT_SUPERUSER = env('ROCKETCHAT_SUPERUSER')
ROCKETCHAT_PASSWORD = env('ROCKETCHAT_PASSWORD')
JITSI_SERVER = env('JITSI_SERVER')
CHAT_AUTH_TOKEN=env('CHAT_AUTH_TOKEN')
BAJAJ_ALLIANZ_AUTH_TOKEN=env('BAJAJ_ALLIANZ_AUTH_TOKEN')
MATRIX_USER_AUTH_TOKEN=env('MATRIX_USER_AUTH_TOKEN')
ODBC_BASE_URL=env('ODBC_BASE_URL')
LAL_PATH_BASE_URL=env('LAL_PATH_BASE_URL')
LAL_PATH_USERNAME=env('LAL_PATH_USERNAME')
LAL_PATH_PASSWORD=env('LAL_PATH_PASSWORD')
LAL_PATH_DATA_API_KEY=env('LAL_PATH_DATA_API_KEY')
LAL_PATH_INTEGRATION_ENABLED=env.bool('LAL_PATH_INTEGRATION_ENABLED')
LAL_PATH_INVOICE_CODE=env('LAL_PATH_INVOICE_CODE')
SIMS_BASE_URL = env('SIMS_BASE_URL')
MEDANTA_DOCTOR_LIST_URL=env('MEDANTA_DOCTOR_LIST_URL')
MEDANTA_DOCTOR_LIST_USER_HEADER=env('MEDANTA_DOCTOR_LIST_USER_HEADER')
MEDANTA_DOCTOR_LIST_USER_VALUE=env('MEDANTA_DOCTOR_LIST_USER_VALUE')
MEDANTA_DOCTOR_LIST_PASSWORD_HEADER=env('MEDANTA_DOCTOR_LIST_PASSWORD_HEADER')
MEDANTA_DOCTOR_LIST_PASSWORD_VALUE=env('MEDANTA_DOCTOR_LIST_PASSWORD_VALUE')
MEDANTA_API_BASE_URL=env('MEDANTA_API_BASE_URL')
MEDANTA_INTEGRATION_ENABLED=env.bool('MEDANTA_INTEGRATION_ENABLED')
ECS_COMM_API_KEY=env('ECS_COMM_API_KEY')
LENSFIT_COUPONS=env.list('LENSFIT_COUPONS')
SPO_DP_AUTH_TOKEN = env('SPO_DP_AUTH_TOKEN')
CARE_PLAN_FOR_VIP=env('CARE_PLAN_FOR_VIP')
VIP_SALESPOINT_URL=env('VIP_SALESPOINT_URL')
VIP_SALESPOINT_AUTHTOKEN=env('VIP_SALESPOINT_AUTHTOKEN')
DOCTORS_COUNT=env('DOCTORS_COUNT')
LAB_COUNT=env('LAB_COUNT')
VIP_CANCELLATION_PERIOD=env.int('VIP_CANCELLATION_PERIOD')
USE_SLAVE_DB=env.bool('USE_SLAVE_DB', False)
RABBITMQ_LOGS_QUEUE=env('RABBITMQ_LOGS_QUEUE')
TRUECALLER_SOURCES=env.list('TRUECALLER_SOURCES')
RABBITMQ_TRACKING_QUEUE=env('RABBITMQ_TRACKING_QUEUE')
SBIG_AUTH_TOKEN=env('SBIG_AUTH_TOKEN')
