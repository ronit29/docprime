from ondoc.chat import models
from ondoc.doctor import models as doc_models
from ondoc.api.v1.doctor import serializers as doc_serializers
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
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

    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated, )
    queryset = doc_models.Doctor.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = doc_models.Doctor.objects.all().order_by('id')[:20]
        # serializer = serializers.DoctorListSerializer(queryset, many=True)
        serializer = doc_serializers.DoctorProfileSerializer(queryset, many=True, context={"request": request})

        return Response(serializer.data)


class DoctorProfileViewSet(viewsets.GenericViewSet):

    queryset = doc_models.DoctorMapping.objects

    def retrieve(self, request, pk):
        doc_mapping = get_object_or_404(doc_models.DoctorMapping, doctor__id=pk)
        response = []
        doctor = doc_mapping.profile_to_be_shown
        if doctor:
            serializer = doc_serializers.DoctorProfileSerializer(doctor, many=False, context={"request": request})
            response = serializer.data
        return Response(response)