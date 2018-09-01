from config.settings.base import *
import logging


API_ENABLED=True
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['qa.panaceatechno.com', 'crmqa.panaceatechno.com', 'docqa.panaceatechno.com', 'qa.docprime.com', 'crmqa.docprime.com', 'docqa.docprime.com','liveqa.docprime.com','livecrm.docprime.com','local.docprime.com'])
EMAIL_BACKEND = 'ondoc.sendemail.backends.backend.WhiteListedEmailBackend'
SMS_BACKEND = 'ondoc.sms.backends.backend.WhitelistedSmsBackend'

EMAIL_WHITELIST = env.list('EMAIL_WHITELIST')
NUMBER_WHITELIST = env.list('NUMBER_WHITELIST')

#S3 Settings
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_QUERYSTRING_AUTH = False
S3_USE_SIGV4 = True
AWS_DEFAULT_ACL = "public-read"
AWS_S3_REGION_NAME='ap-south-1'
# AWS_S3_ENCRYPTION = True
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_S3_CUSTOM_DOMAIN = 's3.%s.amazonaws.com/%s' % (AWS_S3_REGION_NAME, AWS_STORAGE_BUCKET_NAME)
AWS_PRELOAD_METADATA = False


DEFAULT_FILE_STORAGE = 'config.settings.storage_backends.MediaStorage'
STATICFILES_STORAGE = 'config.settings.storage_backends.StaticStorage'
AWS_STATIC_LOCATION = 'static'
STATIC_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, AWS_STATIC_LOCATION)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/tmp/django_cache',
    }
}

CLOUDFRONT_DOMAIN = "qacdn.docprime.com"
#CLOUDFRONT_ID = "your cloud front id"
AWS_S3_CUSTOM_DOMAIN = "qacdn.docprime.com" # to make sure the url that the files are served from this domain

RAVEN_MIDDLEWARE = ['raven.contrib.django.raven_compat.middleware.SentryResponseErrorIdMiddleware']

# Sentry Configuration
SENTRY_DSN = env('DJANGO_SENTRY_DSN')
SENTRY_CLIENT = env('DJANGO_SENTRY_CLIENT', default='raven.contrib.django.raven_compat.DjangoClient')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'root': {
        'level': 'WARNING',
        'handlers': ['sentry'],
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s  %(asctime)s  %(module)s '
                      '%(process)d  %(thread)d  %(message)s'
        },
    },
    'handlers': {
        'sentry': {
            'level': 'ERROR', # To capture more than ERROR, change to WARNING, INFO, etc.
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
            'tags': {'custom-tag': 'x'},
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
        'raven': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
        'sentry.errors': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

SENTRY_CELERY_LOGLEVEL = env.int('DJANGO_SENTRY_LOG_LEVEL', logging.INFO)
RAVEN_CONFIG = {
    'CELERY_LOGLEVEL': env.int('DJANGO_SENTRY_LOG_LEVEL', logging.INFO),
    'DSN': SENTRY_DSN,
    #'release': raven.fetch_git_sha(os.path.abspath(os.pardir)),
}

# SILKY_AUTHENTICATION = True  # User must login
# SILKY_AUTHORISATION = True  # User must have permissions
# SILKY_META = True
# SILKY_PYTHON_PROFILER = True
# SILKY_PYTHON_PROFILER_BINARY = True
# SILKY_PYTHON_PROFILER_RESULT_PATH = os.path.join(str(ROOT_DIR), "silk")

# SILKY_MAX_RECORDED_REQUESTS = 10**4
# SILKY_MAX_RECORDED_REQUESTS_CHECK_PERCENT = 10

# MIDDLEWARE += ['silk.middleware.SilkyMiddleware']