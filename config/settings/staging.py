from config.settings.production import *
DEBUG = env.bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['qa.panaceatechno.com', 'crmqa.panaceatechno.com', 'docqa.panaceatechno.com', 'qa.docprime.com', 'crmqa.docprime.com', 'docqa.docprime.com','live.qa.docprime.com'])
EMAIL_BACKEND = 'ondoc.sendemail.backends.backend.WhiteListedEmailBackend'
SMS_BACKEND = 'ondoc.sms.backends.backend.WhitelistedSmsBackend'

EMAIL_WHITELIST = env.list('EMAIL_WHITELIST')
NUMBER_WHITELIST = env.list('NUMBER_WHITELIST')