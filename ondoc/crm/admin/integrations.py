from django.contrib import admin
from ondoc.integrations.models import IntegratorMapping
from ondoc.integrations.models import IntegratorProfileMapping, IntegratorReport
from ondoc.diagnostic.models import LabTest, Lab, LabPricingGroup, AvailableLabTest
from django import forms
from django.conf import settings


class IntegratorMappingForm(forms.ModelForm):
    test = forms.ModelChoiceField(queryset=LabTest.objects.filter(is_package=False, id__in=list(map(lambda available_lab_test: available_lab_test.test_id, AvailableLabTest.objects.select_related('test').filter(
            lab_pricing_group__in=Lab.objects.filter(network_id=int(settings.THYROCARE_NETWORK_ID)).values_list('lab_pricing_group', flat=True))))).all())


class IntegratorMappingAdmin(admin.ModelAdmin):
    model = IntegratorMapping
    form = IntegratorMappingForm
    list_display = ('integrator_class_name', 'integrator_test_name', 'is_active',)
    fields = ('test', 'integrator_test_name', 'is_active',)
    readonly_fields = ('integrator_test_name',)
    autocomplete_fields = ['test']


class IntegratorProfileMappingForm(forms.ModelForm):
    package = forms.ModelChoiceField(queryset=LabTest.objects.filter(is_package=True, id__in=list(map(lambda available_lab_test: available_lab_test.test_id, AvailableLabTest.objects.select_related('test').filter(
            lab_pricing_group__in=Lab.objects.filter(network_id=int(settings.THYROCARE_NETWORK_ID)).values_list('lab_pricing_group', flat=True))))).all())


class IntegratorProfileMappingAdmin(admin.ModelAdmin):
    model = IntegratorProfileMapping
    form = IntegratorProfileMappingForm
    list_display = ('integrator_class_name', 'integrator_package_name', 'is_active',)
    fields = ('package', 'integrator_package_name', 'is_active',)
    readonly_fields = ('integrator_package_name',)
    # autocomplete_fields = ['package']


class IntegratorReportAdmin(admin.ModelAdmin):
    model = IntegratorReport
    list_display = ('booking_id', 'integrator_name', 'pdf_url', 'xml_url')
    readonly_fields = ('booking_id', 'lead_id', 'pdf_url', 'xml_url')
    search_fields = ['integrator_response__object_id']
    fields = ('booking_id', 'lead_id', 'pdf_url', 'xml_url')

    def booking_id(self, obj):
        return obj.integrator_response.object_id

    def lead_id(self, obj):
        return obj.integrator_response.lead_id

    def integrator_name(self, obj):
        return obj.integrator_response.integrator_class_name
