from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_module
from django.conf import settings
from ondoc.sendemail.backends.backend import ConsoleEmailBackend

def send_email(to, subject, message):
    return get_connection().send_email(subject, message, 'support@docprime.com', to)

def get_connection():
    path = settings.EMAIL_BACKEND
    try:
        mod_name, klass_name = path.rsplit('.', 1)
        mod = import_module(mod_name)
    except AttributeError as e:
        raise ImproperlyConfigured('Error importing sms backend module %s: "%s"' % (mod_name, e))

    try:
        klass = getattr(mod, klass_name)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s" class' % (mod_name, klass_name))

    return klass()
