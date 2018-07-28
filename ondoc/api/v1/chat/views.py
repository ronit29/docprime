from ondoc.chat import models
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.api.v1.doctor import serializers as doc_serializers
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from . import serializers
from django.conf import settings
import requests
import json

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
        doctor = get_object_or_404(doc_models.Doctor, id=pk)
        response = []
        doc_mapping = doc_models.DoctorMapping.objects.filter(doctor=doctor)
        if doc_mapping.exists():
            doctor = doc_mapping.first().profile_to_be_shown
        if doctor:
            serializer = doc_serializers.DoctorProfileSerializer(doctor, many=False, context={"request": request})
            response = serializer.data
        return Response(response)


class UserProfileViewSet(viewsets.GenericViewSet):

    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated, )

    def retrieve(self, request):
        user_id = request.user.id
        chat_domain = settings.CHAT_API_URL
        try:
            chat_api_url = '%s/api/v1/livechat/healthservices/getProfileChats/%s'%(chat_domain, user_id)
            chat_api_request = requests.get(chat_api_url)
        except:
            return Response([])
        try:
            chat_room_url = '%s/api/v1/livechat/healthservices/getRooms/%s'%(chat_domain, user_id)
            chat_room_request = requests.get(chat_room_url)
        except:
            return Response([])
        if chat_api_request.status_code == 200 and chat_room_request.status_code == 200:
            chat_api_json = chat_api_request.text
            chat_room_json = chat_room_request.text
            if chat_api_json and chat_room_json:
                UserProfiles = auth_models.UserProfile.objects.all()
                Doctors = doc_models.Doctor.objects.all()
                chat_api_data = json.loads(chat_api_json)
                chat_room_data = json.loads(chat_room_json)
                response_data = []
                for room_data in chat_room_data:
                    response = {}
                    response['room_id'] = room_data.get('rid', None)
                    response['date'] = room_data.get('ts', None)
                    response['doctor_name'] = None
                    response['user_name']=  None
                    doc_id = room_data.get('user', None)
                    if doc_id:
                        for doc in Doctors:
                            if doc.id == doc_id:
                                response['doctor_name'] = doc.name
                    for chat_data in chat_api_data:
                        if room_data.get('rid') == chat_data.get('_id'):
                            response['symptoms'] = chat_data['params'].get('Symptoms', None)
                            selected_profile = chat_data['params'].get('selectedProfile', None)
                            if selected_profile:
                                user_profile_id = selected_profile.get('id')
                                for usr in UserProfiles:
                                    if usr.id == user_profile_id:
                                        response['user_name'] = usr.name

                    response_data.append(response)
                return Response(response_data)
        return Response([])

