from reversion.admin import VersionAdmin

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
    class Media:
        extend = False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'dynamic_content/init.js')
        css = {'all': ('lab_test/css/style.css',)}


class NewDynamicAdmin(VersionAdmin):
    model = NewDynamic
    forms = NewDynamicAdminForm
    list_display = ['url', 'is_enabled']
    autocomplete_fields = ['url']
    search_fields = ['url__url']





    # class DynamicContentAdminForm(forms.ModelForm):
    #     class Media:
    #         extend = False
    #         js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'dynamic_content/init.js')
    #         css = {'all': ('lab_test/css/style.css',)}
    #
    # #
    # # class DynamicContentInline(TabularInline):
    # #     model = DynamicContent
    # #     form = DynamicContentAdminForm
    # #     extra = 0
    # #     can_delete = True
    # #     autocomplete_fields = ['url']
    # class DynamicContentAdmin(admin.ModelAdmin):
    #     model = DynamicContent
    #     form = DynamicContentAdminForm
    #     list_display = ['title', 'is_enabled']
    #     # inlines = [DynamicContentInline]
    #     raw_id_fields = ('url',)
    #     search_fields = ['url']
    #     # autocomplete_fields = ['url']