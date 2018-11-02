from ondoc.seo.models import SitemapManger
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
