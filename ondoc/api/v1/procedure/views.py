from rest_framework.viewsets import GenericViewSet, ModelViewSet
import re
from django.db.models.functions import StrIndex
from django.db.models import Value, Q
from ondoc.api.pagination import paginate_queryset
from ondoc.api.v1.procedure.serializers import DoctorClinicProcedureSerializer, DoctorClinicProcedureDetailSerializer
from ondoc.procedure.models import Procedure, DoctorClinicProcedure
from rest_framework.response import Response
from ondoc.api.v1.procedure import serializers as procedure_serializer


class ProcedureListViewSet(GenericViewSet):

    def get_queryset(self):
        return Procedure.objects.all().prefetch_related('categories')

    def list(self, request):
        name = request.query_params.get('name', None)

        procedure_data = dict()
        if name:
            search_key = re.findall(r'[a-z0-9A-Z.]+', name)
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            procedure_queryset = Procedure.objects.filter(
                Q(search_key__icontains=search_key) |
                Q(search_key__icontains=' ' + search_key) |
                Q(search_key__istartswith=search_key)).annotate(search_index=StrIndex('search_key', Value(search_key))
                                                                ).order_by('search_index')
            procedure_queryset = paginate_queryset(procedure_queryset, request)
        else:
            procedure_queryset = self.get_queryset()[:20]

        procedure_list_serializer = procedure_serializer.ProcedureInSerializer(procedure_queryset, many=True)
        procedure_data['procedures'] = procedure_list_serializer.data
        return Response(procedure_data)


class DoctorClinicProcedureViewSet(ModelViewSet):
    serializer_class = DoctorClinicProcedureSerializer
    queryset = DoctorClinicProcedure.objects.all()

    def details(self, request):
        serializer = DoctorClinicProcedureDetailSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        result = DoctorClinicProcedureSerializer(self.get_queryset().filter(**validated_data), many=True)
        return Response(result.data)
