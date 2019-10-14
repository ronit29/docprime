from django.contrib import admin

from ondoc.diagnostic.models import AvailableLabTest
from ondoc.salespoint.models import SalesPoint, SalespointTestmapping
from django import forms


class SalesPointAdmin(admin.ModelAdmin):
    model = SalesPoint
    list_display = ['name', 'spo_code']


class SalesPointAvailableTestMappingAdmin(admin.ModelAdmin):
    model = SalespointTestmapping
    list_display = ['salespoint', 'available_tests']

    def get_form(self, request, obj=None, **kwargs):

        form = super(SalesPointAvailableTestMappingAdmin, self).get_form(request, obj=obj, **kwargs)
        form.base_fields['available_tests'].queryset = AvailableLabTest.objects.filter(enabled=True, test__is_package=True, test__enable_for_retail=True)

        return form