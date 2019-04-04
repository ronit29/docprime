from django.contrib import admin
from ondoc.salespoint.models import SalesPoint, SalespointTestmapping
from django import forms


class SalesPointAdmin(admin.ModelAdmin):
    model = SalesPoint
    list_display = ['name', 'spo_code']


class SalesPointAvailableTestMappingAdmin(admin.ModelAdmin):
    model = SalespointTestmapping
    list_display = ['salespoint', 'available_lab_test']