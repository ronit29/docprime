from config.settings.base import *
# from .base import env
API_ENABLED=True
DEBUG = env.bool('DJANGO_DEBUG', default=True)
SECRET_KEY = env('DJANGO_SECRET_KEY', default='!!!SET DJANGO_SECRET_KEY!!!')
CRISPY_FAIL_SILENTLY = not DEBUG

ALLOWED_HOSTS = ['*']
GOOGLE_MAPS_API_KEY = 'AIzaSyDJ06gynqhKmoEQc9tLf60_irFdrXwq_p4'

TEMPLATES[0]['OPTIONS']['debug'] = DEBUG
# SECURE_SSL_REDIRECT=True
# SESSION_COOKIE_SECURE=True
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
INSTALLED_APPS += ('django_extensions',)
INSTALLED_APPS += ('debug_toolbar',)
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

DEBUG_TOOLBAR_CONFIG = {
    'DISABLE_PANELS': [
        'debug_toolbar.panels.redirects.RedirectsPanel',
    ],
    'SHOW_TEMPLATE_CONTEXT': True,
}

INTERNAL_IPS = ['127.0.0.1']

SMS_BACKEND = 'ondoc.sms.backends.backend.ConsoleSmsBackend'
# SMS_BACKEND = 'ondoc.sms.backends.backend.SmsBackend'
EMAIL_BACKEND = 'ondoc.sendemail.backends.backend.ConsoleEmailBackend'
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
#EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'localhost'
# EMAIL_PORT = 1025

# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'handlers': {
#         'file': {
#             'level': 'ERROR',
#             'class': 'logging.FileHandler',
#             'filename': '../djangologs/debug.log',
#         },
#     },
#     'loggers': {
#         'django': {
#             'handlers': ['file'],
#             'level': 'DEBUG',
#             'propagate': True,
#         },
#     },
# }



# RABBITMQ_CONNECTION_SETTINGS = {
#     'CONNECTION_URL': 'amqp://guest:guest@localhost:5672/%2F',
#     'NOTIFICATION_QUEUE': 'notifications'
# }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
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
        'sentry': {
            'level': 'INFO',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
        'console': {
            'level': 'INFO',
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
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

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

}

RATING_SMS_NOTIF=env('RATING_SMS_NOTIF_QA', default=60)
THYROCARE_NETWORK_ID = 1