from django.contrib import admin
from import_export import resources, fields
from import_export.admin import ImportMixin
from import_export.formats import base_formats

from ondoc.location.models import EntityUrls
from ondoc.web.models import Career, OnlineLead, UploadImage, TinyUrl
from django.utils.safestring import mark_safe

# Register your models here.


class CareerAdmin(admin.ModelAdmin):
    list_display = ('name', 'profile_type', 'created_at')
    # readonly_fields=('onboarding_status', )
    list_filter = ('profile_type', 'created_at')

    readonly_fields = ['name', 'mobile', 'email', 'profile_type', 'resume', 'created_at']
    fields = ['name','mobile', 'email', 'profile_type', 'resume', 'created_at']


class OnlineLeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_type', 'city', 'city_name', 'created_at')

    readonly_fields = ['name', 'city', 'city_name', 'mobile', 'email', 'member_type', 'created_at']
    fields = ['name', 'city', 'city_name', 'mobile', 'email', 'member_type', 'created_at']


class UploadImageAdmin(admin.ModelAdmin):
    date_hierarchy = 'created_at'
    list_display = ('id', 'name',)
    fields = ('name', 'image', 'url')
    readonly_fields = ('url',)

    def url(self, instance):
        if instance and instance.id:
            url = instance.image.path if instance.image else None
            if url:
                return mark_safe('''<a href="%s" target='_blank'>%s</a>''' % (url, url))
        return None
    url.short_description = "Url"

admin.site.register(OnlineLead, OnlineLeadAdmin)
admin.site.register(Career, CareerAdmin)
admin.site.register(UploadImage, UploadImageAdmin)
admin.site.register(TinyUrl)

#
# class EntityUrlsResource(resources.ModelResource):
#
#     url = fields.Field(attribute='url', column_name='url')
#     extras = fields.Field(attribute='extras', column_name='extras')
#     is_valid = fields.Field(attribute='is_valid', column_name='is_valid')
#     url_type = fields.Field(attribute='url_type', column_name='url_type')
#     entity_type = fields.Field(attribute='entity_type', column_name='entity_type')
#     entity_id = fields.Field(attribute='entity_id', column_name='entity_id')
#     created_at = fields.Field(attribute='created_at', column_name='created_at')
#     updated_at = fields.Field(attribute='updated_at', column_name='updated_at')
#     count = fields.Field(attribute='count', column_name='count')
#     sitemap_identifier = fields.Field(attribute='sitemap_identifier', column_name='sitemap_identifier')
#     sequence = fields.Field(attribute='sequence', column_name='sequence')
#
#
#     class Meta:
#         model = EntityUrls
#         import_id_fields = ('id',)
#         exclude = ('created_at', 'updated_at', 'locality_latitude', 'locality_longitude', 'sublocality_value', 'locality_value'
#                    , 'locality_id', 'sublocality_id', 'specialization', 'specialization_id','sublocality_latitude', 'sublocality_longitude')
#
#
# from django.contrib.gis import admin
#
#
# class EntityUrlsAdmin(ImportMixin, admin.ModelAdmin):
#     formats = (base_formats.CSV, base_formats.XLSX,)
#     list_display = ('url', 'extras', 'is_valid', 'url_type', 'entity_type', 'entity_id', 'created_at', 'updated_at',
#                    'count', 'sitemap_identifier', 'sequence')
#     resource_class = EntityUrlsResource
#
# admin.site.register(EntityUrls, EntityUrlsAdmin)