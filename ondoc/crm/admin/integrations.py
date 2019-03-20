from django.contrib import admin
from ondoc.integrations.models import IntegratorMapping
from ondoc.integrations.models import IntegratorProfileMapping, IntegratorReport


class IntegratorMappingAdmin(admin.ModelAdmin):
    model = IntegratorMapping
    list_display = ('integrator_class_name', 'integrator_test_name', 'is_active',)
    fields = ('test', 'integrator_test_name', 'is_active',)
    readonly_fields = ('integrator_test_name',)
    autocomplete_fields = ['test']


class IntegratorProfileMappingAdmin(admin.ModelAdmin):
    model = IntegratorProfileMapping
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
