from config.settings.base import *
import logging


SECRET_KEY = env('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['panaceatechno.com', 'docprime.com','admin.docprime.com'])
DATABASES['default']['ATOMIC_REQUESTS'] = True  # noqa F405
DATABASES['default']['CONN_MAX_AGE'] = env.int('CONN_MAX_AGE', default=60)  # noqa F405
DEBUG = False

EMAIL_BACKEND = 'ondoc.sendemail.backends.backend.MailgunEmailBackend'

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
#SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-ssl-redirect
#SECURE_SSL_REDIRECT = env.bool('DJANGO_SECURE_SSL_REDIRECT', default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
#SESSION_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
#SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
#CSRF_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
# CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/topics/security/#ssl-https
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-seconds
# TODO: set this to 60 seconds first and then to 518400 once you prove the former works
#SECURE_HSTS_SECONDS = 60
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-include-subdomains
#SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-preload
#SECURE_HSTS_PRELOAD = env.bool('DJANGO_SECURE_HSTS_PRELOAD', default=True)
# https://docs.djangoproject.com/en/dev/ref/middleware/#x-content-type-options-nosniff
SECURE_CONTENT_TYPE_NOSNIFF = env.bool('DJANGO_SECURE_CONTENT_TYPE_NOSNIFF', default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-browser-xss-filter
SECURE_BROWSER_XSS_FILTER = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = 'DENY'

if env('ENABLE_DATADOG', default=False):
    INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + ('ddtrace.contrib.django',) + LOCAL_APPS 

INSTALLED_APPS += ('gunicorn',)

SMS_BACKEND = 'ondoc.sms.backends.backend.SmsBackend'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'root': {
        'level': 'WARNING',
        'handlers': ['console', ],
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s '
                      '%(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console', ],
            'propagate': False,
        },
        'raven': {
            'level': 'DEBUG',
            'handlers': ['console', ],
            'propagate': False,
        },
        'sentry.errors': {
            'level': 'DEBUG',
            'handlers': ['console', ],
            'propagate': False,
        },
        'django.security.DisallowedHost': {
            'level': 'ERROR',
            'handlers': ['console', ],
            'propagate': False,
        },
    },
}

if env('ENABLE_SENTRY', default=False):
    INSTALLED_APPS += ('raven.contrib.django.raven_compat',)
    RAVEN_MIDDLEWARE = ['raven.contrib.django.raven_compat.middleware.SentryResponseErrorIdMiddleware']
    MIDDLEWARE = RAVEN_MIDDLEWARE + MIDDLEWARE
    # Sentry Configuration
    SENTRY_DSN = env('DJANGO_SENTRY_DSN')
    SENTRY_CLIENT = env('DJANGO_SENTRY_CLIENT', default='raven.contrib.django.raven_compat.DjangoClient')
    SENTRY_CELERY_LOGLEVEL = env.int('DJANGO_SENTRY_LOG_LEVEL', logging.INFO)
    RAVEN_CONFIG = {
        'CELERY_LOGLEVEL': env.int('DJANGO_SENTRY_LOG_LEVEL', logging.INFO),
        'DSN': SENTRY_DSN,
        # 'release': raven.fetch_git_sha(os.path.abspath(os.pardir)),
    }
    LOGGING['handlers']['sentry'] = {
                                    'level': 'ERROR',
                                    'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
                                     }
    LOGGING['loggers']['django.security.DisallowedHost']['handlers'] = ['console', 'sentry', ]
    LOGGING['root']['handlers'] = ['sentry', ]


EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

GOOGLE_ANALYTICS_PROPERTY_ID = 'UA-14845987-3'



AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_QUERYSTRING_AUTH = False
S3_USE_SIGV4 = True
AWS_DEFAULT_ACL = "public-read"
AWS_S3_REGION_NAME='ap-south-1'
# AWS_S3_ENCRYPTION = True
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

CLOUDFRONT_DOMAIN = "cdn.docprime.com"
#CLOUDFRONT_ID = "your cloud front id"
AWS_S3_CUSTOM_DOMAIN = "cdn.docprime.com" # to make sure the url that the files are served from this domain

AWS_HEADERS = {
    'Cache-Control': 'max-age=31536000',
}
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=31536000',
}

RATING_SMS_NOTIF=env('RATING_SMS_NOTIF_PRD', default=86400)
THYROCARE_NETWORK_ID = 43

