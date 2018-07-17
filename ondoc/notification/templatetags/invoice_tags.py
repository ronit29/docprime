from django import template
from ondoc.doctor.models import OpdAppointment
from ondoc.authentication.models import UserProfile

register = template.Library()


@register.filter
def subtract(value, arg):
    return round(value - arg, 2)


@register.filter
def mode_of_payment(payment_type):
    payment_mode_mapping = {choice[0]: choice[1] for choice in OpdAppointment.PAY_CHOICES}
    return payment_mode_mapping[int(payment_type)]


@register.filter
def get_gender(gender):
    if not gender:
        return ""
    payment_mode_mapping = {choice[0]: choice[1] for choice in UserProfile.GENDER_CHOICES}
    return payment_mode_mapping[gender]
