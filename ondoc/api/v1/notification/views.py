from itertools import groupby

from ondoc.notification import models
from ondoc.api.v1.utils import IsNotAgent
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ondoc.api.pagination import paginate_queryset
from rest_framework import viewsets
from django.utils import timezone
from django.db import transaction
from . import serializers
from rest_framework import status


class AppNotificationViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.AppNotificationSerializer
    permission_classes = (IsAuthenticated, IsNotAgent)

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
        return Response(result)

    def get_queryset(self):
        request = self.request
        return models.AppNotification.objects.filter(user=request.user)

    @transaction.non_atomic_requests
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
        viewed_at = read_at
        required_notifications_ids = request.data.get("notificationids", None)
        if required_notifications_ids:
            required_notifications_ids = AppNotificationViewSet.get_notification_ids_list(required_notifications_ids)
            self.get_queryset().filter(pk__in=required_notifications_ids, viewed_at__isnull=True).update(viewed_at=viewed_at)
            self.get_queryset().filter(pk__in=required_notifications_ids, read_at__isnull=True).update(read_at=read_at)
        else:
            self.get_queryset().filter(viewed_at__isnull=True).update(viewed_at=viewed_at)
            self.get_queryset().filter(read_at__isnull=True).update(read_at=read_at)
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return AppNotificationViewSet.append_unviewed_unread_count(serializer.data, queryset)


class ChatNotificationViewSet(viewsets.GenericViewSet):

    def chat_send(self, request):
        from ondoc.authentication.models import NotificationEndpoint
        from ondoc.communications.models import PUSHNotification, NotificationAction

        data = request.data

        if not data or not data.get('title') or not data.get('body') or not data.get('room_id') or not data.get('user_id'):
            return Response({"message":"Insufficient Data"}, status=status.HTTP_400_BAD_REQUEST)

        user_id = data.get('user_id')
        user_and_tokens = []
        user_and_token = [{'user': token.user, 'token': token.token, 'app_name': token.app_name} for token in
                          NotificationEndpoint.objects.filter(user__in=[user_id]).order_by('user')]
        for user, user_token_group in groupby(user_and_token, key=lambda x: x['user']):
            user_and_tokens.append(
                {'user': user, 'tokens': [{"token": t['token'], "app_name": t["app_name"]} for t in user_token_group]})

        context = {
            "title" : data.get('title'),
            "body" : data.get('body'),
            "screen": data.get('screen', "chat"),
            "room_id": data.get('room_id'),
            "data_only": True
        }
        noti = PUSHNotification(NotificationAction.CHAT_NOTIFICATION, context)
        noti.send(user_and_tokens)
        return Response({"message": "Notification Sent"})

