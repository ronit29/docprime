from reversion.admin import VersionAdmin
from ondoc.notification.models import DynamicTemplates


class EmailNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', 'email', )
    search_fields = ('user', 'notification_type', )


class SmsNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', 'phone_number', )
    search_fields = ('user', 'notification_type', )


class PushNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', )
    search_fields = ('user', 'notification_type', )


class AppNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', )
    search_fields = ('user', 'notification_type', )


class DynamicTemplatesAdmin(VersionAdmin):
    model = DynamicTemplates
    list_display = ('template_type', 'template_name', 'preview_url')
    fields = ('template_type', 'template_name', 'content', 'sample_parameters', 'approved')

    def save_model(self, request, obj, form, change):
        responsible_user = request.user
        obj.created_by = responsible_user if responsible_user and not responsible_user.is_anonymous else None

        super().save_model(request, obj, form, change)
