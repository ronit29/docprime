from django.contrib import admin
from reversion.admin import VersionAdmin

from ondoc.crm.admin.doctor import AutoComplete
from ondoc.location.models import CityInventory, EntityUrls, CityLatLong

# Register your models here.

admin.site.register(CityInventory)
admin.site.register(CityLatLong)



class EntityUrlsAdmin(AutoComplete, VersionAdmin):
    model = EntityUrls
    search_fields = ['url', 'url_value']
