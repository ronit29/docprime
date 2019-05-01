from django.contrib.admin import TabularInline
# from django.contrib.auth import admin
from django.contrib import admin

from ondoc.corporate_booking.models import CorporateBooking, CorporateDeal, CorporateDocument


class CorporateDocumentInline(TabularInline):
    model = CorporateDocument
    extra = 0
    can_delete = True
    verbose_name = 'Corporate Document'
    verbose_name_plural = 'Corporate Documents'


class CorporateBookingAdmin(admin.ModelAdmin):
    model = CorporateBooking
    list_display = ['corporate_name']
    inlines = [CorporateDocumentInline]


class CorporateDealAdmin(admin.ModelAdmin):
    model = CorporateDeal


