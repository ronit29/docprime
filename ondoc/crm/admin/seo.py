from ondoc.seo.models import SitemapManger
import datetime
from django.contrib import admin


class SitemapManagerAdmin(admin.ModelAdmin):
    model = SitemapManger
    list_display = ['file', 'count']
    fields = ['file']

    def save_model(self, request, obj, form, change):
        obj.file.name = '%s-%s' % (str(datetime.datetime.utcnow()), obj.file.name)
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super(SitemapManagerAdmin, self).get_queryset(request)

        return qs.filter(valid=True)