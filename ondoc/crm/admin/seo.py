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
    readonly_fields = ['url', 'admin_page']

    def admin_page(self, obj):
        from ondoc.doctor.models import Hospital
        from django.urls import reverse
        from django.utils.safestring import mark_safe
        admin_link = None
        if obj and obj.url_value:
            entity_obj = EntityUrls.objects.filter(url=obj.url_value,
                                                   sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE,
                                                   is_valid=True).first()
            if not entity_obj:
                return admin_link
            hosp_obj = Hospital.objects.filter(id=entity_obj.entity_id).first()
            if not hosp_obj:
                return admin_link
            exit_point_url = reverse('admin:{}_{}_change'.format("doctor", "hospital"), kwargs={"object_id": hosp_obj.id})
            admin_link = mark_safe("<a href={} target='_blank'>{}</a>".format(exit_point_url, hosp_obj.name))
        return admin_link

