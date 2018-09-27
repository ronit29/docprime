from django.contrib import admin
from ondoc.web.models import Career, OnlineLead, UploadImage, TinyUrl
from django.utils.safestring import mark_safe

# Register your models here.


class CareerAdmin(admin.ModelAdmin):
    list_display = ('name', 'profile_type', 'created_at')
    # readonly_fields=('onboarding_status', )
    list_filter = ('profile_type', 'created_at')

    readonly_fields = ['name', 'mobile', 'email', 'profile_type', 'resume', 'created_at']
    fields = ['name','mobile', 'email', 'profile_type', 'resume', 'created_at']

class OnlineLeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_type', 'city', 'city_name', 'created_at')

    readonly_fields = ['name', 'city', 'city_name', 'mobile', 'email', 'member_type', 'created_at']
    fields = ['name', 'city', 'city_name', 'mobile', 'email', 'member_type', 'created_at']

class UploadImageAdmin(admin.ModelAdmin):
    date_hierarchy = 'created_at'

    list_display = ('name', 'url', 'created_at')
    #
    def url(self, instance):
        url = None
        if instance and instance.id:
            url = instance.image.path
        return mark_safe('''<a href="%s" target='_blank'>%s</a>'''%(url, url))
    url.short_description = "Url"

admin.site.register(OnlineLead, OnlineLeadAdmin)
admin.site.register(Career, CareerAdmin)
admin.site.register(UploadImage, UploadImageAdmin)
admin.site.register(TinyUrl)
