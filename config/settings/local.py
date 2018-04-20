from .base import *
from .base import env

DEBUG = env.bool('DJANGO_DEBUG', default=True)
SECRET_KEY = env('DJANGO_SECRET_KEY', default='!!!SET DJANGO_SECRET_KEY!!!')

ALLOWED_HOSTS = ['*']
GOOGLE_MAPS_API_KEY = 'AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA'

TEMPLATES[0]['OPTIONS']['debug'] = DEBUG

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