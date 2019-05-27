from dal import autocomplete
from reversion.admin import VersionAdmin

from ondoc.location.models import EntityUrls
from ondoc.seo.models import SitemapManger, NewDynamic
from ondoc.seo.models import SeoLabNetwork
import datetime
from django.contrib import admin
from django import forms



class SitemapManagerAdmin(admin.ModelAdmin):
    model = SitemapManger
    list_display = ['file', 'count']
    fields = ['file']

    def get_queryset(self, request):
        qs = super(SitemapManagerAdmin, self).get_queryset(request)

        return qs.filter(valid=True)


class SeoSpecializationAdmin(admin.ModelAdmin):
    model = SitemapManger
    list_display = ['specialization']
    fields = ['specialization']

class SeoLabNetworkAdmin(admin.ModelAdmin):

    model = SeoLabNetwork
    list_display = ['lab_network','rank']


class NewDynamicAdminForm(forms.ModelForm):
    top_content = forms.CharField(widget=forms.Textarea, required=False)
    bottom_content = forms.CharField(widget=forms.Textarea, required=False)
    # url_value = forms.ModelChoiceField(queryset=EntityUrls.objects.all(), widget=autocomplete.ListSelect2(url='entity-compare-autocomplete'))
    url_value = forms.CharField()
    dropdown = forms.CharField(widget=forms.HiddenInput, required=False)

    class Media:
        extend = True
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'new_dynamic/js/init.js')
        css = {'all': ('new_dynamic/css/style.css',)}
        # widgets = {
        #     'url_value': autocomplete.ModelSelect2(url='entity-compare-autocomplete')
        # }


class NewDynamicAdmin(admin.ModelAdmin):
    model = NewDynamic
    form = NewDynamicAdminForm
    list_display = ['id', 'url_value', 'is_enabled']
    autocomplete_fields = ['url']
    # search_fields = ['url__url', 'url_value__url']
    # exclude = ['url_value']
    # readonly_fields = ['url_value']
    readonly_fields = ['url']



