from rest_framework import serializers
from ondoc.notification import models


class EmailNotificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.EmailNotification
        fields = "__all__"


class SmsNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SmsNotification
        fields = "__all__"


class PushNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PushNotification
        fields = "__all__"


class AppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AppNotification
        fields = "__all__"
