from rest_framework.viewsets import GenericViewSet
import re
from django.db.models.functions import StrIndex
from django.db.models import Value,Q
from ondoc.api.pagination import paginate_queryset
from ondoc.procedure.models import Procedure
from rest_framework.response import Response
from ondoc.api.v1.procedure.serializers import serializers as procedure_serializer


class ProcedureListViewSet(GenericViewSet):

    def list(self, request):
        name = request.query_params.get('name')
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
            procedure_queryset = self.queryset[:20]

        procedure_list_serializer = procedure_serializer.ProcedureListSerializer(procedure_queryset, many=True)
        procedure_data['procedures'] = procedure_list_serializer.data
        return Response(procedure_data)