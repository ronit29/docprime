from ondoc.tracking import models as track_models
from rest_framework.response import Response
from rest_framework import status
from . import serializers
from rest_framework.viewsets import GenericViewSet


class EventCreateViewSet(GenericViewSet):

    def create(self, request):
        serializer = serializers.EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        event_data = validated_data.get('data')
        if event_data:
            pass
        return Response()



