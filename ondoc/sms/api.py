from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_module


def send_sms(message, phone_no):

    # print(message)
    # return True
    return get_connection().send_message(message, phone_no)


def send_otp(message, phone_no):

    # print(message)
    # return True
    if str(phone_no) not in settings.OTP_BYPASS_NUMBERS:
        return get_connection().send_otp(message, phone_no)


def get_connection():
    path = settings.SMS_BACKEND
    try:
        mod_name, klass_name = path.rsplit('.', 1)
        mod = import_module(mod_name)
    except AttributeError as e:
        raise ImproperlyConfigured(u'Error importing sms backend module %s: "%s"' % (mod_name, e))

    try:
        klass = getattr(mod, klass_name)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s" class' % (mod_name, klass_name))

    return klass()
