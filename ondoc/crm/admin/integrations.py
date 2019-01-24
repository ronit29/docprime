from django.contrib import admin
from ondoc.integrations.models import IntegratorMapping


class IntegratorMappingAdmin(admin.ModelAdmin):
    model = IntegratorMapping
    list_display = ('integrator_class_name', 'integrator_test_name', 'is_active',)
    fields = ('test', 'integrator_test_name', 'is_active')

    readonly_fields = ('integrator_test_name', )
