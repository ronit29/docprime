from config.settings.production import *

# ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['qa.panaceatechno.com', 'crmqa.panaceatechno.com', 'docqa.panaceatechno.com', 'qa.docprime.com', 'crmqa.docprime.com', 'docqa.docprime.com','liveqa.docprime.com','livecrm.docprime.com','local.docprime.com'])
ALLOWED_HOSTS = ['*']
EMAIL_BACKEND = 'ondoc.sendemail.backends.backend.WhiteListedEmailBackend'
SMS_BACKEND = 'ondoc.sms.backends.backend.WhitelistedSmsBackend'

DEBUG=False
EMAIL_WHITELIST = env.list('EMAIL_WHITELIST')
NUMBER_WHITELIST = env.list('NUMBER_WHITELIST')


CLOUDFRONT_DOMAIN = "qacdn.docprime.com"
#CLOUDFRONT_ID = "your cloud front id"
AWS_S3_CUSTOM_DOMAIN = "qacdn.docprime.com" # to make sure the url that the files are served from this domain

RATING_SMS_NOTIF=env('RATING_SMS_NOTIF_QA', default=30)
THYROCARE_NETWORK_ID = 43

DATABASES['default']['CONN_MAX_AGE'] = 0
