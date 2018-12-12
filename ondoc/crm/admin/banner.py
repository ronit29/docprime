from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from import_export import fields, resources
from ondoc.banner.models import Banner
from ondoc.diagnostic.models import LabAppointment, Lab
from ondoc.doctor.models import OpdAppointment, Doctor
from django import forms
from import_export.admin import ImportExportMixin, ImportExportActionModelAdmin



class BannerAdmin(admin.ModelAdmin):

    model = Banner
    list_display = ['title', 'object_id', 'start_date', 'end_date']