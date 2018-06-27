from ondoc.chat import models
from ondoc.doctor import models as doc_models
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from . import serializers

User = get_user_model()


class ChatSearchedItemsViewSet(viewsets.GenericViewSet):

    def list(self, request, *args, **kwargs):
        medical_conditions = models.ChatMedicalCondition.objects.all().values("id", "name")
        return Response({"conditions": medical_conditions})


class DoctorsListViewSet(viewsets.GenericViewSet):

    permission_classes = (IsAuthenticated, )
    queryset = doc_models.Doctor.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = doc_models.Doctor.objects.all().order_by('id')[:20]
        serializer = serializers.DoctorListSerializer(queryset, many=True)

        return Response(serializer.data)