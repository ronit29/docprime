from config.settings.base import *
# from .base import env

DEBUG = env.bool('DJANGO_DEBUG', default=True)
SECRET_KEY = env('DJANGO_SECRET_KEY', default='!!!SET DJANGO_SECRET_KEY!!!')
CRISPY_FAIL_SILENTLY = not DEBUG

ALLOWED_HOSTS = ['*']
GOOGLE_MAPS_API_KEY = 'AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA'

TEMPLATES[0]['OPTIONS']['debug'] = DEBUG
# SECURE_SSL_REDIRECT=True
# SESSION_COOKIE_SECURE=True
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# INSTALLED_APPS += ('debug_toolbar',)
# MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

# DEBUG_TOOLBAR_CONFIG = {
#     'DISABLE_PANELS': [
#         'debug_toolbar.panels.redirects.RedirectsPanel',
#     ],
#     'SHOW_TEMPLATE_CONTEXT': True,
# }

INTERNAL_IPS = ['127.0.0.1']

SMS_BACKEND = 'ondoc.sms.backends.backend.ConsoleSmsBackend'
# SMS_BACKEND = 'ondoc.sms.backends.backend.SmsBackend'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
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
INSTALLED_APPS += ('django_extensions',)
INSTALLED_APPS += ('rest_framework_swagger',)

SWAGGER_SETTINGS = {
    'USE_SESSION_AUTH': True,
}
