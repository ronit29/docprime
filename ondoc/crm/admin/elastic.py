from django.contrib.gis import admin
from ondoc.elastic.models import DemoElastic


class DemoElasticAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', )
    display = ()
    model = DemoElastic
