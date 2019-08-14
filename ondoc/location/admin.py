from django.contrib import admin
from django import forms
from reversion.admin import VersionAdmin
import re
from ondoc.crm.admin.doctor import AutoComplete
from ondoc.crm.constants import constants
from ondoc.location.models import CityInventory, EntityUrls, CityLatLong

# Register your models here.

admin.site.register(CityInventory)
admin.site.register(CityLatLong)


class EntityUrlsAdminForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        value = self.cleaned_data
        if not re.match("^[a-z0-9\-_]+$", value.get('url', "")):
                raise forms.ValidationError("Invalid URL.")
        if self.instance.id and self.instance.sitemap_identifier == self.instance.SitemapIdentifier.HOSPITAL_PAGE:
            if not value.get('url', "").endswith("-hpp"):
                raise forms.ValidationError("Invalid URL for hospital.")
        if EntityUrls.objects.filter(url=value.get('url')).exists():
            raise forms.ValidationError("Entered URL already exists.")
        return value


class EntityUrlsAdmin(AutoComplete, VersionAdmin):
    model = EntityUrls
    form = EntityUrlsAdminForm
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
