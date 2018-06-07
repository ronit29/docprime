from ondoc.chat import models
from rest_framework import mixins, viewsets, status
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import get_user_model
User = get_user_model()


class ChatSearchedItemsViewSet(viewsets.GenericViewSet):

    def list(self, request, *args, **kwargs):
        medical_conditions = models.ChatMedicalCondition.objects.all().values("id", "name")
        return Response({"conditions": medical_conditions})