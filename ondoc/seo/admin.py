from django.contrib import admin

from .models import Sitemap, Robot
# Register your models here.

class SitemapAdmin(admin.ModelAdmin):
    model = Sitemap

    fields = ('file', 'created_at', 'updated_at')
    list_display = ('file', 'created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        fields = ['created_at', 'updated_at']
        if obj:
            fields = fields+['file']
        return fields

    def get_queryset(self, request):
       return Sitemap.objects.all().order_by('-created_at')


class RobotAdmin(admin.ModelAdmin):
    model = Robot

    fields = ('file', 'created_at', 'updated_at')
    list_display = ('file', 'created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        fields = ['created_at', 'updated_at']
        if obj:
            fields = fields+['file']
        return fields

    def get_queryset(self, request):
       return Robot.objects.all().order_by('-created_at')






admin.site.register(Sitemap, SitemapAdmin)
admin.site.register(Robot, RobotAdmin)