from django.contrib import admin
from ondoc.integrations.models import IntegratorMapping


class IntegratorMappingAdmin(admin.ModelAdmin):
    model = IntegratorMapping
    list_display = ('integrator_class_name', 'test', 'content_object')
    fields = ('test', 'integrator_test_name')
