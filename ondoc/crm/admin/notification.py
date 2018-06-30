from reversion.admin import VersionAdmin


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
