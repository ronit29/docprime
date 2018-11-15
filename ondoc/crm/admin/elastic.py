from django.contrib.gis import admin
from ondoc.elastic.models import DemoElastic
from import_export import resources, fields
from import_export.admin import ImportMixin, base_formats, ImportExportMixin
from django.contrib.gis.geos import Point


class DemoElasticAdmin(ImportMixin, admin.ModelAdmin):
    list_display = ('id', 'created_at', )
    display = ()
    resource_class = DemoElastic
