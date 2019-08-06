from django.contrib import admin
from reversion.admin import VersionAdmin

from ondoc.crm.admin.doctor import AutoComplete
from ondoc.crm.constants import constants
from ondoc.location.models import CityInventory, EntityUrls, CityLatLong

# Register your models here.

admin.site.register(CityInventory)
admin.site.register(CityLatLong)



class EntityUrlsAdmin(AutoComplete, VersionAdmin):
    model = EntityUrls
    search_fields = ['url', 'url_value', 'entity_id']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_member_of(constants['ARTICLE_TEAM']):
            queryset = queryset.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE)
        return queryset

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if request.user.is_member_of(constants['ARTICLE_TEAM']):
            fields = ['url', 'is_valid']
        return fields
