from config.settings.production import *
DEBUG = env.bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['qa.panaceatechno.com', 'crmqa.panaceatechno.com', 'docqa.panaceatechno.com', 'qa.docprime.com', 'crmqa.docprime.com', 'docqa.docprime.com'])