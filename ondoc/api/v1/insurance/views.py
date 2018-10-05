from rest_framework import viewsets
from . import serializers
from rest_framework.response import Response
from ondoc.insurance.models import Insurer
from ondoc.insurance.models import InsurancePlans


class ListInsuranceViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return Insurer.objects.filter()

    def list(self, request):
        insurer_data = self.get_queryset()
        body_serializer = serializers.InsurerSerializer(insurer_data, many=True)

        # body_serializer.is_valid(raise_exception=True)
        # valid_data = body_serializer.validated_data
        return Response(body_serializer.data)


