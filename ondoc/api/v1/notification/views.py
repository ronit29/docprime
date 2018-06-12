from ondoc.notification import models
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ondoc.api.pagination import paginate_queryset
from rest_framework import viewsets
from django.utils import timezone
from . import serializers


class AppNotificationViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.AppNotificationSerializer
    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        request = self.request
        return models.AppNotification.objects.filter(user=request.user)

    def list(self, request):
        viewed_time = timezone.now()
        models.AppNotification.objects.filter(user=request.user, viewed_at__isnull=True
                                              ).update(viewed_at=viewed_time)
        queryset = self.get_queryset()
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return Response(serializer.data)