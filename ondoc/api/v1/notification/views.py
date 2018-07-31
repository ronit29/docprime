from ondoc.notification import models
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ondoc.api.pagination import paginate_queryset
from rest_framework import viewsets
from django.utils import timezone
from . import serializers


class AppNotificationViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.AppNotificationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        request = self.request
        return models.AppNotification.objects.filter(user=request.user)

    def list(self, request):
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        result = dict()
        result["data"] = serializer.data
        result["unread_count"] = queryset.filter(read_at__isnull=True).count()
        result["unviewed_count"] = queryset.filter(viewed_at__isnull=True).count()
        return Response(result)

    def mark_notifications_as_viewed(self, request):
        viewed_time = timezone.now()
        req_notifications_ids = request.data.get("notificationids", None)
        if req_notifications_ids:
            req_notifications_ids = req_notifications_ids.split(',')
            if not isinstance(req_notifications_ids, list):
                req_notifications_ids = [req_notifications_ids]
            self.get_queryset().filter(pk__in=req_notifications_ids, viewed_at__isnull=True).update(
                viewed_at=viewed_time)
        else:
            self.get_queryset().filter(viewed_at__isnull=True).update(viewed_at=viewed_time)

        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        result = dict()
        result["data"] = serializer.data
        result["unread_count"] = queryset.filter(read_at__isnull=True).count()
        result["unviewed_count"] = queryset.filter(viewed_at__isnull=True).count()
        return Response(result)

    def mark_notifications_as_read(self, request):
        read_at = timezone.now()
        req_notifications_ids = request.data.get("notificationids", None)
        if req_notifications_ids:
            req_notifications_ids = req_notifications_ids.split(',')
            if not isinstance(req_notifications_ids, list):
                req_notifications_ids = [req_notifications_ids]
            self.get_queryset().filter(pk__in=req_notifications_ids, read_at__isnull=True).update(read_at=read_at)
        else:
            self.get_queryset().filter(read_at__isnull=True).update(read_at=read_at)

        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        result = dict()
        result["data"] = serializer.data
        result["unread_count"] = queryset.filter(read_at__isnull=True).count()
        result["unviewed_count"] = queryset.filter(viewed_at__isnull=True).count()
        return Response(result)