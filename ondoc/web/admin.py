from django.contrib import admin
from ondoc.web.models import Career, OnlineLead
# Register your models here.


class CareerAdmin(admin.ModelAdmin):
    list_display = ('name', 'profile_type', 'created_at')
    # readonly_fields=('onboarding_status', )
    list_filter = ('profile_type', 'created_at')

    readonly_fields = ['name', 'mobile', 'email', 'profile_type', 'resume', 'created_at']
    fields = ['name','mobile', 'email', 'profile_type', 'resume', 'created_at']

class OnlineLeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_type', 'created_at')
    # readonly_fields=('onboarding_status', )
    list_filter = ('member_type', 'created_at')

    readonly_fields = ['name', 'mobile', 'email', 'member_type', 'created_at']
    fields = ['name','mobile', 'email', 'member_type', 'created_at']



admin.site.register(OnlineLead, OnlineLeadAdmin)
admin.site.register(Career, CareerAdmin)
