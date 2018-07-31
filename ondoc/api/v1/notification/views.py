from ondoc.notification import models
from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
from ondoc.api.pagination import paginate_queryset
from rest_framework import viewsets
from django.utils import timezone
from . import serializers


class AppNotificationViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.AppNotificationSerializer
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def get_notification_ids_list(ids):
        ids = ids.split(',')
        if not isinstance(ids, list):
            ids = [ids]
        ids = [int(id_) for id_ in ids]
        return ids

    @staticmethod
    def append_unviewed_unread_count(data, queryset):
        result = dict()
        result["data"] = data
        result["unread_count"] = queryset.filter(read_at__isnull=True).count()
        result["unviewed_count"] = queryset.filter(viewed_at__isnull=True).count()
        return result

    def get_queryset(self):
        request = self.request
        return models.AppNotification.objects.filter(user=request.user)

    def list(self, request):
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return AppNotificationViewSet.append_unviewed_unread_count(serializer.data, queryset)

    def mark_notifications_as_viewed(self, request):
        viewed_time = timezone.now()
        required_notifications_ids = request.data.get("notificationids", None)
        if required_notifications_ids:
            required_notifications_ids = AppNotificationViewSet.get_notification_ids_list(required_notifications_ids)
            self.get_queryset().filter(pk__in=required_notifications_ids, viewed_at__isnull=True).update(
                viewed_at=viewed_time)
        else:
            self.get_queryset().filter(viewed_at__isnull=True).update(viewed_at=viewed_time)
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return AppNotificationViewSet.append_unviewed_unread_count(serializer.data, queryset)

    def mark_notifications_as_read(self, request):
        read_at = timezone.now()
        required_notifications_ids = request.data.get("notificationids", None)
        if required_notifications_ids:
            required_notifications_ids = AppNotificationViewSet.get_notification_ids_list(required_notifications_ids)
            self.get_queryset().filter(pk__in=required_notifications_ids, read_at__isnull=True).update(read_at=read_at)
        else:
            self.get_queryset().filter(read_at__isnull=True).update(read_at=read_at)
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return AppNotificationViewSet.append_unviewed_unread_count(serializer.data, queryset)
