from django.contrib import admin
from ondoc.integrations.models import IntegratorMapping
from ondoc.integrations.models import IntegratorProfileMapping, IntegratorReport, IntegratorTestMapping, \
    IntegratorTestParameterMapping, IntegratorDoctorMappings, IntegratorHospitalMappings
from ondoc.diagnostic.models import LabTest, Lab, LabPricingGroup, AvailableLabTest
from django import forms
from django.conf import settings


class IntegratorMappingForm(forms.ModelForm):
    test = forms.ModelChoiceField(
        queryset=LabTest.objects.filter(is_package=False, availablelabs__lab_pricing_group__labs__network_id=int(settings.THYROCARE_NETWORK_ID),
                                        enable_for_retail=True, availablelabs__enabled=True).distinct())


class IntegratorMappingAdmin(admin.ModelAdmin):
    model = IntegratorMapping
    form = IntegratorMappingForm
    list_display = ('integrator_class_name', 'integrator_test_name', 'is_active',)
    fields = ('test', 'integrator_test_name', 'is_active',)
    readonly_fields = ('integrator_test_name',)
    autocomplete_fields = ['test']


class IntegratorProfileMappingForm(forms.ModelForm):
    package = forms.ModelChoiceField(
        queryset=LabTest.objects.filter(is_package=True, availablelabs__lab_pricing_group__labs__network_id=int(settings.THYROCARE_NETWORK_ID),
                                        enable_for_retail=True, availablelabs__enabled=True).distinct())


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('integrator_response')
        return qs

    def booking_id(self, obj):
        return obj.integrator_response.object_id

    def lead_id(self, obj):
        return obj.integrator_response.lead_id

    def integrator_name(self, obj):
        return obj.integrator_response.integrator_class_name


# class IntegratorTestMappingForm(forms.ModelForm):
#     test = forms.ModelChoiceField(
#         queryset=LabTest.objects.filter(availablelabs__lab_pricing_group__labs__network_id=int(
#             settings.THYROCARE_NETWORK_ID), enable_for_retail=True, availablelabs__enabled=True).distinct())
#
#     # def __init__(self, *args, **kwargs):
#     #     super().__init__(*args, **kwargs)


# class ThyrocareTestAutocomplete(autocomplete.Select2QuerySetView):
#
#     def get_queryset(self):
#         queryset = LabTest.objects.filter(availablelabs__lab_pricing_group__labs__network_id=int(settings.THYROCARE_NETWORK_ID), enable_for_retail=True, availablelabs__enabled=True).distinct()
#         return queryset


class IntegratorTestMappingForm(forms.ModelForm):
    test = forms.ModelChoiceField(
        queryset=LabTest.objects.filter(availablelabs__lab_pricing_group__labs__network_id=int(settings.THYROCARE_NETWORK_ID),
                                        enable_for_retail=True, availablelabs__enabled=True).distinct().order_by('name'))


class IntegratorTestMappingAdmin(admin.ModelAdmin):
    model = IntegratorTestMapping
    list_display = ('integrator_class_name', 'integrator_test_name', 'is_active')
    fields = ('test', 'integrator_test_name', 'is_active', 'integrator_test_type')
    form = IntegratorTestMappingForm
    readonly_fields = ('integrator_test_name', 'integrator_test_type')

    def integrator_test_type(self, obj):
        return obj.test_type


class IntegratorTestParameterMappingAdmin(admin.ModelAdmin):
    model = IntegratorTestParameterMapping
    list_display = ['integrator_test_name', 'integrator_class_name']
    readonly_fields = ('integrator_test_name',)
    autocomplete_fields = ['test_parameter']


class IntegratorDoctorMappingsAdmin(admin.ModelAdmin):
    model = IntegratorDoctorMappings
    list_display = ('first_name', 'last_name', 'is_active', 'integrator_class_name')
    fields = ('first_name', 'middle_name', 'last_name', 'hospital_name', 'city', 'is_active', 'qualification', 'specialities', 'address',
              'primary_contact', 'secondary_contact', 'emergency_contact', 'helpline_sos', 'integrator_class_name',
              'integrator_doctor_id', 'integrator_hospital_id', 'integrator_doctor_data', 'doctor_clinic')
    readonly_fields = ('first_name', 'middle_name', 'last_name', 'hospital_name', 'city', 'qualification', 'specialities', 'address',
                       'primary_contact', 'secondary_contact', 'emergency_contact', 'helpline_sos', 'integrator_class_name',
                       'integrator_doctor_id', 'integrator_hospital_id', 'integrator_doctor_data')
    autocomplete_fields = ['doctor_clinic']


class IntegratorHospitalMappingsAdmin(admin.ModelAdmin):
    model = IntegratorHospitalMappings
    list_display = ('integrator_class_name', 'integrator_hospital_name', 'is_active')
    fields = ('hospital', 'integrator_hospital_name', 'is_active', 'integrator_class_name')
    autocomplete_fields = ['hospital']
