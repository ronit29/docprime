from django.contrib import admin

# Register your models here.
from django.contrib.contenttypes.admin import GenericTabularInline

from ondoc.doctor.models import OpdAppointment
from ondoc.ratings_review.models import RatingsReview


class AppointmentRatingInline(GenericTabularInline):
    can_delete = False
    extra = 0
    model = RatingsReview
    fields = ['ratings']

