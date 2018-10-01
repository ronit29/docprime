from django.contrib.gis import admin
from ondoc.geoip.models import AdwordLocationCriteria
from import_export import resources, fields
from import_export.admin import ImportMixin, base_formats, ImportExportMixin
from django.contrib.gis.geos import Point


class AdwordLocationCriteriaResource(resources.ModelResource):
    criteria_id = fields.Field(attribute='criteria_id', column_name='Criteria ID')
    name = fields.Field(attribute='name', column_name='Name')
    cannonical_name = fields.Field(attribute='cannonical_name', column_name='Canonical Name')
    parent_id = fields.Field(attribute='parent_id', column_name='Parent ID')
    country_code = fields.Field(attribute='country_code', column_name='Country Code')
    target_type = fields.Field(attribute='target_type', column_name='Target Type')
    status = fields.Field(attribute='status', column_name='Status')
    latitude = fields.Field(attribute='latitude', column_name='Latitude')
    longitude = fields.Field(attribute='longitude', column_name='Longitude')

    class Meta:
        model = AdwordLocationCriteria
        import_id_fields = ('criteria_id',)
        exclude = ('created_at', 'updated_at', 'latlong')

    def before_save_instance(self, instance, using_transactions, dry_run):
        print(instance.name)
        if instance.latitude and instance.longitude:
            instance.latlong = Point(instance.longitude, instance.latitude)
        super().before_save_instance(instance, using_transactions, dry_run)


class AdwordLocationCriteriaAdmin(ImportMixin, admin.ModelAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name', )
    resource_class = AdwordLocationCriteriaResource
