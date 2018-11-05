from ondoc.seo.models import SitemapManger
from ondoc.seo.models import SeoLabNetwork
import datetime
from django.contrib import admin


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