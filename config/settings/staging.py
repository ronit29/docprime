from config.settings.production import *
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
AWS_PRELOAD_METADATA = True


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
