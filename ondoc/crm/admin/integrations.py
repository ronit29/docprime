from django.contrib import admin
from ondoc.integrations.models import IntegratorMapping
from ondoc.integrations.models import IntegratorProfileMapping


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
    autocomplete_fields = ['package']