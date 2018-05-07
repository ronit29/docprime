from .serializers import LabTestSerializer, LabTestListSerializer
from rest_framework import viewsets
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from ondoc.diagnostic.models import LabTest

class PathologyTestList(viewsets.ReadOnlyModelViewSet):
    queryset = LabTest.objects.all()
    serializer_class= LabTestSerializer
    lookup_field = 'id'

    # def list(self, request):
    # # Note the use of `get_queryset()` instead of `self.queryset`
    #     queryset = self.get_queryset()
    #     serializer = PathologyTestListSerializer(queryset, many=True)
    #     return Response(serializer.data)

    # def detail(self, request, id):    
    #     queryset = self.get_queryset().filter(pk=id)
    #     obj = get_object_or_404(queryset)

    #     serializer = PathologyTestSerializer(obj)
    #     return Response(serializer.data)
